"""100명 합성 프로필과 매칭 서버에 대한 검증 (실제 OpenAI 호출 없음)."""
import http.client
import json
import os
import sqlite3
from contextlib import closing
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import matchmaking
import team_database
import server

VALID = {
    'competencies': [
        {'name': 'Python 프로그래밍', 'evidence': 'Python 데이터 전처리', 'evidence_level': '명확'},
        {'name': '데이터 분석 능력', 'evidence': 'CSV 파일 가공', 'evidence_level': '명확'},
    ],
    'contests': [
        {'id': 'c1', 'title': 'AI 프로그래밍 개발 공모전', 'category': 'AI·개발'},
        {'id': 'c2', 'title': '서비스 디자인 공모전', 'category': '디자인'},
    ],
}


class TestTeamDatabase(unittest.TestCase):
    def test_database_is_hundred_synthetic_members(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'demo.sqlite'
            team_database.seed_database(path)
            profiles = team_database.get_members(path)
            self.assertEqual(len(profiles), 100)
            self.assertEqual(len({m['id'] for m in profiles}), 100)
            self.assertEqual(len({m['nickname'] for m in profiles}), 100)
            self.assertTrue(all(m['is_synthetic'] and len(m['skills']) == 3 and m['university'] and m['major'] and m['grade'] for m in profiles))
            self.assertTrue(all('email' not in m for m in profiles))
            self.assertTrue(all(m['email'].endswith('@example.com') for m in team_database.get_members(path, include_email=True)))
            with closing(sqlite3.connect(path)) as con, con:
                self.assertEqual(con.execute('SELECT count(*) FROM member_skills').fetchone()[0], 300)
                self.assertEqual(con.execute('SELECT count(*) FROM team_members').fetchone()[0], 100)
                self.assertEqual(con.execute('SELECT count(*) FROM member_interests').fetchone()[0], sum(len(m['interests']) for m in profiles))
            team_database.seed_database(path)
            self.assertEqual(len(team_database.get_members(path)), 100)

    def test_existing_ten_preserved(self):
        for old in team_database.FAKE_MEMBERS:
            found = next(m for m in team_database.get_members() if m['id'] == old['id'])
            self.assertEqual(found['nickname'], old['nickname'])
            self.assertEqual(found['major'], old['major'])

    def test_match_estimates_and_validation(self):
        validated = matchmaking.validate_match_input(VALID)
        result = matchmaking.match_estimates(validated)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(0 < r['score'] <= 94 and r['source'] == 'rules' and r['member']['is_synthetic'] for r in result))
        self.assertTrue(all(r['member']['id'].startswith('TM') for r in result))
        for invalid in [
            {'competencies': 'bad', 'contests': VALID['contests']},
            {'competencies': VALID['competencies'], 'contests': []},
            {'competencies': VALID['competencies'], 'contests': VALID['contests'] * 3},
        ]:
            with self.assertRaises(ValueError):
                matchmaking.validate_match_input(invalid)

    def test_ai_match_is_based_only_on_skills_not_personal_data(self):
        seen, chosen = [], []

        def fake_ai(system, payload, schema, name):
            seen.append(json.dumps(payload, ensure_ascii=False))
            self.assertEqual(name, 'chemi_teammate_matches_v2')
            self.assertEqual(len(payload['candidate_pools']), 2)
            self.assertTrue(all(len(x['candidates']) <= 16 for x in payload['candidate_pools']))
            output = []
            for group in payload['candidate_pools']:
                cid = group['contest_id']
                mid = group['candidates'][0]['id']
                chosen.append(mid)
                output.append({'contest_id': cid, 'member_id': mid, 'score': 84, 'reason': '상호보완 역량이 있어요.'})
            return {'matches': output}

        recs = matchmaking.ai_matches(matchmaking.validate_match_input(VALID), fake_ai)
        self.assertEqual([x['member']['id'] for x in recs], chosen)
        self.assertTrue(all(x['source'] == 'ai' for x in recs))
        self.assertNotIn('example.com', seen[0])
        self.assertNotIn('김하린', seen[0])
        self.assertNotIn('학과', seen[0])
        self.assertNotIn('campus', seen[0])

    def test_ai_reason_internal_candidate_id_is_not_shown(self):
        def fake_ai(system, payload, schema, name):
            result=[]
            for group in payload['candidate_pools']:
                chosen=group['candidates'][0]['id']
                result.append({'contest_id':group['contest_id'], 'member_id':chosen,
                               'reason':f'사용자의 역량과 후보 {chosen}로 역할을 보완할 수 있습니다.'})
            return {'matches':result}
        results=matchmaking.ai_matches(matchmaking.validate_match_input(VALID),fake_ai)
        self.assertEqual(len(results),2)
        self.assertTrue(all(x['source']=='ai' for x in results))
        self.assertTrue(all('TM0' not in x['reason'] for x in results))
        self.assertTrue(all(x['member']['id'] not in x['reason'] for x in results))
        self.assertTrue(all('역할' in x['reason'] or '역량' in x['reason'] for x in results))

    def test_ai_reason_without_id_is_preserved(self):
        self.assertEqual(matchmaking.safe_public_reason('부족한 디자인 역량을 보완합니다.', '대체 이유'), '부족한 디자인 역량을 보완합니다.')
        self.assertEqual(matchmaking.safe_public_reason('후보 TM090로 도움이 됩니다.', '역할 근거'), '역할 근거')
        self.assertEqual(matchmaking.safe_public_reason('550e8400-e29b-41d4-a716-446655440000 팀원', '역할 근거'), '역할 근거')

    def test_ai_rejects_candidate_outside_shortlist(self):
        def fake_ai(system, payload, schema, name):
            listed = {r['id'] for r in payload['candidate_pools'][0]['candidates']}
            outside = next(m['id'] for m in team_database.get_members() if m['id'] not in listed)
            return {'matches': [{'contest_id': 'c1', 'member_id': outside, 'score': 99, 'reason': '임의 선택'}]}

        results = matchmaking.ai_matches(matchmaking.validate_match_input(VALID), fake_ai)
        self.assertEqual(results[0]['source'], 'rules')


class TestMatchEndpoints(unittest.TestCase):
    def setUp(self):
        # The recommendation endpoint tests use synthetic profiles and a mocked
        # model. They must not query the user's real Supabase environment.
        offline = patch.object(server.cloud_store, 'configured', return_value=False)
        local_host = patch.object(server, 'HOST', '127.0.0.1')
        offline.start()
        local_host.start()
        self.addCleanup(local_host.stop)
        self.addCleanup(offline.stop)

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), server.ChemiHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def req(self, route, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        headers = headers or {}
        if body is None:
            conn.request('GET', route)
        else:
            headers = {'Content-Type': 'application/json', **headers}
            conn.request('POST', route, json.dumps(body, ensure_ascii=False).encode(), headers)
        resp = conn.getresponse()
        value = resp.read()
        status = resp.status
        conn.close()
        return status, json.loads(value)

    def test_members_endpoint(self):
        status, payload = self.req('/api/team/members')
        self.assertEqual(status, 200)
        self.assertEqual(payload['count'], 100)
        self.assertEqual(len(payload['members']), 100)
        self.assertTrue(all('email' not in m for m in payload['members']))

    def test_match_endpoint_rejects_missing_header(self):
        self.assertEqual(self.req('/api/team/match', VALID)[0], 403)
        self.assertEqual(self.req('/api/team/match', VALID, {'X-CHEMI-Request': '1', 'Origin': 'http://malicious.example'})[0], 403)

    def test_ai_match_http_with_mock_model(self):
        def fake_ai(system, payload, schema, name):
            return {'matches': [{'contest_id': pool['contest_id'], 'member_id': pool['candidates'][0]['id'],
                                 'score': 85, 'reason': '부족한 기술을 보완합니다.'}
                                for pool in payload['candidate_pools']]}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-local-test-key'}), patch.object(server, 'call_openai', side_effect=fake_ai) as mocked:
            status, data = self.req('/api/team/match', {**VALID, 'mode': 'ai'}, {'X-CHEMI-Request': '1'})
            self.assertEqual(status, 200)
            self.assertEqual(len(data['matches']), 2)
            self.assertTrue(all(m['source'] == 'ai' for m in data['matches']))
            self.assertEqual(mocked.call_count, 1)

    def test_match_endpoint_without_api_key_uses_heuristic(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
            status, data = self.req('/api/team/match', {**VALID, 'mode': 'estimate'}, {'X-CHEMI-Request': '1'})
            self.assertEqual(status, 200)
            self.assertEqual(len(data['matches']), 2)
            self.assertEqual(data['matches'][0]['source'], 'rules')
            self.assertFalse(data['ai_available'])


if __name__ == '__main__':
    unittest.main()
