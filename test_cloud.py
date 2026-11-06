"""Supabase의 실제 비밀번호/키 없이 HTTP 흐름과 계정 분리 확인."""
import http.client
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import cloud_store
import server

UID_A = '123e4567-e89b-12d3-a456-426614174000'
UID_B = '123e4567-e89b-12d3-a456-426614174001'


class TestCloud(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), server.ChemiHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, path, method='GET', data=None, headers=None):
        con = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        body = json.dumps(data, ensure_ascii=False).encode('utf-8') if data is not None else None
        hdr = {'Content-Type': 'application/json', 'X-CHEMI-Request': '1'}
        hdr.update(headers or {})
        con.request(method, path, body=body, headers=hdr)
        r = con.getresponse()
        status, header_pairs, content = r.status, r.getheaders(), r.read()
        con.close()
        return status, json.loads(content), header_pairs

    def test_unconfigured_me_is_demo(self):
        with patch.dict(os.environ, {'SUPABASE_URL': '', 'SUPABASE_PUBLISHABLE_KEY': ''}):
            status, result, _ = self.call('/api/auth/me')
        self.assertEqual(status, 200)
        self.assertFalse(result['configured'])

    def test_unauthenticated_cannot_write_when_configured(self):
        with patch.object(cloud_store, 'configured', return_value=True):
            status, result, _ = self.call('/api/auth/me')
            self.assertEqual(status, 200)
            self.assertFalse(result['authenticated'])
            status, result, _ = self.call('/api/me/profile', 'PUT', {'nickname': '익명'})
            self.assertEqual(status, 401)
            self.assertIn('로그인', result['error'])
            status, result, _ = self.call('/api/interview/question', 'POST', {'stage': 1, 'initial_experience': '프로젝트'})
            self.assertEqual(status, 401)

    def test_signup_with_confirmation(self):
        with patch.object(cloud_store, 'signup', return_value={'user': {'id': UID_A}, 'session': None}):
            status, data, hdr = self.call('/api/auth/signup', 'POST', {'email': 'a@example.com', 'password': 'password1234'})
        self.assertEqual(status, 200)
        self.assertTrue(data['confirmation_required'])
        self.assertFalse([v for k, v in hdr if k.lower() == 'set-cookie'])

    def test_login_and_restoration_separate_per_owner(self):
        sessions = {'access_token':'mock_token_A', 'refresh_token':'mock_refresh_A', 'expires_in':3600,
                    'user':{'id':UID_A,'email':'a@example.com'}}
        store = {UID_A: {'nickname':'학생 A','university':'강원대학교','major':'컴퓨터공학과','grade':'2학년'},
                 UID_B: {'nickname':'학생 B','university':'강원대학교','major':'디자인학과','grade':'4학년'}}
        def verify(tok):
            return {'id': UID_A if tok == 'mock_token_A' else UID_B, 'email': 'a@example.com'}
        def fetch_profile(uid, tok):
            self.assertEqual(uid, UID_A)  # request must never read B's profile
            return store[uid]
        with patch.object(cloud_store,'configured',return_value=True), \
             patch.object(cloud_store,'signin',return_value=sessions), \
             patch.object(cloud_store,'verify_user',side_effect=verify), \
             patch.object(cloud_store,'fetch_profile',side_effect=fetch_profile), \
             patch.object(cloud_store,'fetch_analysis',return_value={'summary':'분석 결과','competencies':[]}):
            status, data, hdr = self.call('/api/auth/login','POST',{'email':'a@example.com','password':'password1234'})
            self.assertEqual(status,200)
            cookies = [v for k, v in hdr if k.lower()=='set-cookie']
            self.assertEqual(len(cookies),2)
            self.assertTrue(all('HttpOnly' in v and 'SameSite=Lax' in v for v in cookies))
            cookie_header = '; '.join(v.split(';',1)[0] for v in cookies)
            status, data, _ = self.call('/api/auth/me',headers={'Cookie':cookie_header})
            self.assertEqual(status,200)
            self.assertTrue(data['authenticated'])
            self.assertEqual(data['profile']['nickname'],'학생 A')
            self.assertEqual(data['analysis']['summary'],'분석 결과')
            self.assertNotIn('학생 B', json.dumps(data,ensure_ascii=False))

    def test_profile_and_analysis_write_belongs_to_authenticated_user(self):
        cookie = 'chemi_access=mock_token_A'
        profile = {'nickname':'학생 A','university':'강원대학교','major':'컴퓨터공학과','grade':'2학년','consent':True}
        analysis = {'summary':'기획 경험', 'competencies':[{'name':'기획','evidence':'직접 기획','evidence_level':'명확'}], 'caution':'예비'}
        interview = {'initial_experience':'프로젝트 참여', 'first_question':'어떤 역할?', 'first_answer':'기획',
                     'additional_experience':'', 'second_question':'', 'second_answer':''}
        with patch.object(cloud_store,'configured',return_value=True), \
             patch.object(cloud_store,'verify_user',return_value={'id':UID_A,'email':'a@example.com'}), \
             patch.object(cloud_store,'save_profile',return_value=profile) as p_save, \
             patch.object(cloud_store,'save_analysis',return_value=True) as a_save, \
             patch.object(server,'analyze_interview',return_value=analysis):
            s, data, _ = self.call('/api/me/profile','PUT',profile,headers={'Cookie':cookie})
            self.assertEqual(s,200)
            self.assertEqual(p_save.call_args.args[0],UID_A)
            s, result, _ = self.call('/api/interview/analyze','POST',interview,headers={'Cookie':cookie})
            self.assertEqual(s,200)
            self.assertTrue(result['saved'])
            self.assertEqual(a_save.call_args.args[0],UID_A)
            self.assertEqual(a_save.call_args.args[2],interview)

    def test_csrf_header_and_origin(self):
        with patch.object(cloud_store,'configured',return_value=True):
            for hdr in ({'X-CHEMI-Request':'0'}, {'Origin':'https://evil.invalid'}):
                status, _, _ = self.call('/api/auth/signup', 'POST', {'email':'test@example.com','password':'password123'}, hdr)
                self.assertEqual(status,403)

    def test_logout_clears_cookie(self):
        with patch.object(cloud_store, 'signout', return_value=None):
            s, data, headers = self.call('/api/auth/logout','POST',{}, {'Cookie':'chemi_access=foo'})
        self.assertEqual(s,200)
        self.assertEqual(len([v for k,v in headers if k.lower() == 'set-cookie' and 'Max-Age=0' in v]),2)

    def test_profile_requires_consent(self):
        with self.assertRaises(cloud_store.CloudError):
            cloud_store.save_profile(UID_A,'token',{'nickname':'A','university':'강원대학교','major':'AI','grade':'2학년','consent':False})


if __name__ == '__main__':
    unittest.main()
