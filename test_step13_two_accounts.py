"""Step 13: end-to-end HTTP flow with two simulated accounts; NEVER contacts Supabase/OpenAI."""
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

import cloud_store
import server

A = '123e4567-e89b-12d3-a456-426614174000'
B = '123e4567-e89b-12d3-a456-426614174001'
C = '123e4567-e89b-12d3-a456-426614174002'
TOKENS = {'token-a': A, 'token-b': B, 'token-c': C}


class FakeSupabase:
    def __init__(self):
        self.profiles = {
            A: {'user_id': A, 'nickname': '테스트A', 'major': '소프트웨어학과'},
            B: {'user_id': B, 'nickname': '테스트B', 'major': '디자인학과'},
            C: {'user_id': C, 'nickname': '테스트C', 'major': '경영학과'},
        }
        self.analysis = {
            A: {'competencies':[{'name':'Python 프로그래밍', 'evidence':'앱 개발 경험', 'evidence_level':'명확'}]},
            B: {'competencies':[{'name':'UI 디자인','evidence':'Figma 화면 제작','evidence_level':'명확'}]},
            C: {'competencies':[{'name':'기획','evidence':'팀 회의','evidence_level':'명확'}]}
        }
        self.public = {}
        self.requests = []
        self.counter = 0

    def who(self, token):
        uid = TOKENS.get(token)
        if not uid:
            raise cloud_store.CloudError('로그인이 필요합니다.', 401)
        return uid

    def handle(self, method, path, data=None, token=None, *, prefer=None):
        uid = self.who(token)
        split = urlsplit(path)
        params = parse_qs(split.query)
        if split.path == '/auth/v1/user':
            return {'id': uid, 'email': f'user-{uid[-1]}@example.com'}
        if split.path == '/rest/v1/chemi_match_profiles':
            # Mimic RLS: viewers without opt-in may not see other public profiles.
            rows = list(self.public.values()) if uid in self.public else []
            filters = params.get('user_id', [])
            if filters:
                prefix, val = filters[0].split('.', 1)
                rows = [x for x in rows if (x['user_id'] == val if prefix == 'eq' else x['user_id'] != val)]
            return rows[:int(params.get('limit', ['1000'])[0])]
        if split.path == '/rest/v1/chemi_match_requests':
            return [dict(x) for x in self.requests if uid in (x['sender_id'],x['recipient_id'])]
        if split.path == '/rest/v1/chemi_analyses':
            return [self.analysis[uid]]
        if split.path == '/rest/v1/chemi_profiles':
            return [self.profiles[uid]]
        if split.path == '/rest/v1/rpc/chemi_set_match_visibility':
            if data['p_enabled']:
                item = self.profiles[uid]
                self.public[uid] = {'user_id': uid, 'nickname': item['nickname'], 'major': item['major'],
                                    'skill_names':[s['name'] for s in self.analysis[uid]['competencies']],
                                    'interests': data['p_interests'], 'opted_in_at':'2026-11-06T00:00:00Z'}
                return {'enabled': True}
            self.public.pop(uid, None)
            self.requests = [x for x in self.requests if uid not in (x['sender_id'], x['recipient_id'])]
            return {'enabled': False}
        if split.path == '/rest/v1/rpc/chemi_send_match_request':
            target = data['p_recipient']
            if uid not in self.public or target not in self.public or uid == target:
                raise cloud_store.CloudError('매칭 참여 동의가 필요합니다.', 400)
            self.counter += 1
            self.requests.append({'id':self.counter,'sender_id':uid,'recipient_id':target,
                    'contest_id':data['p_contest_id'],'contest_title':data['p_contest_title'],
                    'message':data['p_message'], 'status':'pending', 'created_at':'2026-11-06T00:00:00Z'})
            return {'id':self.counter,'status':'pending'}
        if split.path == '/rest/v1/rpc/chemi_respond_match_request':
            record = next((r for r in self.requests if r['id']==data['p_request_id']),None)
            if not record or record['status'] != 'pending':
                raise cloud_store.CloudError('존재하지 않거나 처리된 요청입니다.',400)
            action = data['p_action']
            if (action in ('accepted','declined') and uid != record['recipient_id']) or (action == 'cancelled' and uid != record['sender_id']):
                raise cloud_store.CloudError('권한이 없습니다.',403)
            record['status'] = action
            return {'id':record['id'],'status':action}
        raise AssertionError(f'Unhandled mocked request: {method} {path}')


class TestStep13TwoAccountFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(('127.0.0.1',0), server.ChemiHandler)
        cls.thread=threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.db = FakeSupabase()
        self.config = patch.object(cloud_store,'configured',return_value=True)
        self.network = patch.object(cloud_store,'request',side_effect=self.db.handle)
        self.config.start()
        self.network.start()
        self.addCleanup(self.network.stop)
        self.addCleanup(self.config.stop)

    def call(self, user, method, path, payload=None):
        con = http.client.HTTPConnection('127.0.0.1',self.srv.server_port,timeout=10)
        headers = {'Content-Type':'application/json', 'X-CHEMI-Request':'1'}
        if user: headers['Cookie'] = f'chemi_access=token-{user.lower()}'
        con.request(method,path,body=json.dumps(payload) if payload is not None else None,headers=headers)
        response=con.getresponse()
        status=response.status
        body=json.loads(response.read())
        con.close()
        return status,body

    def test_complete_two_account_request_and_acceptance(self):
        self.assertEqual(self.call('A','POST','/api/me/matching',{'enabled':True,'interests':['AI·개발']})[0],200)
        self.assertEqual(self.call('B','POST','/api/me/matching',{'enabled':True,'interests':['디자인']})[0],200)
        status, diag = self.call('A','GET','/api/me/matching/diagnostics')
        self.assertEqual(status,200)
        self.assertTrue(diag['participating'])
        self.assertEqual(diag['other_candidate_count'],1)
        self.assertNotIn('email',str(diag))
        self.assertNotIn('Figma',str(diag))

        # User C has not opted in, so cannot view profiles or send requests.
        status, diag_c = self.call('C','GET','/api/me/matching/diagnostics')
        self.assertEqual(status,200)
        self.assertFalse(diag_c['participating'])
        self.assertEqual(diag_c['other_candidate_count'],0)

        # Actual matching recommendation uses existing saved AI skills, not forged browser skills.
        status, ranking = self.call('A','POST','/api/team/match',{
            'competencies':[{'name':'브라우저 위조 역량','evidence':'임의 조작'}],
            'contests':[{'id':'contest-42','title':'캠퍼스 디자인 공모전','category':'디자인'}],
            'mode':'estimate'})
        self.assertEqual(status,200)
        self.assertEqual(ranking['real_candidate_count'],1)
        self.assertFalse(ranking['synthetic'])
        self.assertEqual(ranking['matches'][0]['member']['id'],B)
        self.assertNotIn('email',str(ranking))
        self.assertNotIn('interview',str(ranking))

        status, result = self.call('A','POST','/api/team/request',{
            'recipient_id':B,'contest_id':'contest-42','contest_title':'캠퍼스 디자인 공모전','message':''})
        self.assertEqual(status,200)
        req_id = result['result']['id']
        status, inbox = self.call('B','GET','/api/me/requests')
        self.assertEqual(status,200)
        self.assertEqual(inbox['requests'][0]['direction'],'received')
        self.assertEqual(inbox['requests'][0]['status'],'pending')

        # Non-recipient may not accept a request.
        self.assertEqual(self.call('C','POST','/api/team/respond',{'request_id':req_id,'action':'accepted'})[0],403)
        self.assertEqual(self.call('B','POST','/api/team/respond',{'request_id':req_id,'action':'accepted'})[0],200)
        status, sent = self.call('A','GET','/api/me/requests')
        self.assertEqual(status,200)
        self.assertEqual(sent['requests'][0]['status'],'accepted')
        self.assertEqual(sent['requests'][0]['direction'],'sent')
        status, diag = self.call('A','GET','/api/me/matching/diagnostics')
        self.assertEqual(status,200)
        self.assertEqual(diag['request_counts']['accepted'],1)
        self.assertEqual(diag['request_counts']['sent'],1)

        # Withdrawing consent removes B from public matches and associated requests.
        self.assertEqual(self.call('B','POST','/api/me/matching',{'enabled':False,'interests':[]})[0],200)
        status, diag = self.call('A','GET','/api/me/matching/diagnostics')
        self.assertEqual(status,200)
        self.assertEqual(diag['other_candidate_count'],0)
        self.assertEqual(diag['request_counts']['sent'],0)

    def test_diagnostics_rejects_unauthenticated(self):
        status, body = self.call(None,'GET','/api/me/matching/diagnostics')
        self.assertEqual(status,401)
        self.assertIn('error',body)

if __name__ == '__main__':
    unittest.main()
