"""Step 19: matching recommendation explainability and safeguards, offline only."""
import unittest
from unittest.mock import patch
import matchmaking


def member(identifier, *skills, interests=None, synthetic=True):
    return {
        'id': identifier, 'nickname': '시연후보', 'major': '테스트학과',
        'skills': [{'name': name, 'category': category} for name, category in skills],
        'interests': interests or [], 'is_synthetic': synthetic,
    }


class EnhancedMatchingTest(unittest.TestCase):
    def setUp(self):
        self.user = [{'name': 'Python 백엔드 개발', 'evidence': '프로젝트 구현 경험', 'evidence_level': '명확'}]
        self.contest = {'id': 'demo-ai', 'title': 'AI 서비스 개발 및 데이터 활용 공모전', 'category': 'AI·개발'}
        self.same = member('a', ('Python 백엔드 개발', 'AI·개발'), interests=['AI·개발'])
        self.complement = member('b', ('데이터 분석', 'AI·개발'), ('SQL 모델링', 'AI·개발'), interests=['AI·개발'])

    def test_role_complement_preferred_over_duplicate_developer(self):
        score_same, _, breakdown_same = matchmaking.score_candidate(self.contest, self.user, self.same)
        score_other, reason, breakdown_other = matchmaking.score_candidate(self.contest, self.user, self.complement)
        self.assertGreater(score_other, score_same)
        self.assertGreater(breakdown_other['complement'], breakdown_same['complement'])
        self.assertIn('데이터·AI', breakdown_other['filled_roles'])
        self.assertIn('보완', reason)

    def test_score_evidence_absent_zero_not_assumed(self):
        _, _, b = matchmaking.score_candidate(self.contest, self.user, self.complement)
        self.assertEqual(b['experience'], 0)
        self.assertIn('공개 근거', b['evidence_note'])

    def test_category_and_title_only_no_sensitive_member_fields(self):
        sensitive = dict(self.complement, email='hidden@never.example', grade='2학년', notes='개인적인 이야기')
        basic = matchmaking.score_candidate(self.contest, self.user, self.complement)[0]
        self.assertEqual(basic, matchmaking.score_candidate(self.contest, self.user, sensitive)[0])

    def test_no_user_skills_means_zero_score(self):
        score, _, _ = matchmaking.score_candidate(self.contest, [], self.complement)
        self.assertEqual(score, 0)

    def test_same_input_same_ranking_and_breakdown_sums(self):
        pool = [self.same, self.complement]
        ranked = matchmaking.rank_candidates(self.contest, self.user, pool)
        self.assertEqual([r[5]['id'] for r in ranked], [r[5]['id'] for r in matchmaking.rank_candidates(self.contest, self.user, pool)])
        score, _, b = matchmaking.score_candidate(self.contest, self.user, self.complement)
        self.assertEqual(score, sum(b[key] for key in ('complement', 'contest_fit', 'experience', 'interest', 'shared')))
        self.assertLessEqual(score, 100)

    def test_ai_model_cannot_inflate_rule_score(self):
        validated = matchmaking.validate_match_input({'competencies': self.user, 'contests': [self.contest]})
        def fake_ai(system, payload, schema, model_name):
            self.assertIn('candidate_pools', payload)
            self.assertEqual(model_name, 'chemi_teammate_matches_v2')
            return {'matches': [{'contest_id': 'demo-ai', 'member_id': 'b', 'score': 100,
                                 'reason': '공개된 데이터 분석 역량이 개발 역량을 보완합니다.'}]}
        result = matchmaking.ai_matches(validated, fake_ai, members=[self.same, self.complement])[0]
        rule_score = matchmaking.score_candidate(self.contest, self.user, self.complement)[0]
        self.assertEqual(result['score'], rule_score)
        self.assertEqual(result['source'], 'ai')
        self.assertEqual(result['ranking_version'], 'role_complement_v2')
        self.assertIn('breakdown', result)

    def test_ai_outside_top_is_rejected(self):
        # The AI may only choose from shortlisted members; an arbitrary ID is ignored.
        validated = matchmaking.validate_match_input({'competencies': self.user, 'contests': [self.contest]})
        def fake_ai(system, payload, schema, name):
            return {'matches': [{'contest_id': 'demo-ai', 'member_id': 'someone_else', 'reason': 'fake'}]}
        results = matchmaking.ai_matches(validated, fake_ai, members=[self.same, self.complement])
        self.assertEqual(results[0]['source'], 'rules')

if __name__ == '__main__':
    unittest.main()
