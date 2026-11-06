"""Step 21: no-live-network security regression tests for CHEMI.

Run with: python -m unittest test_step21_security.py -v
"""
import http.client
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import cloud_store
import contests
import server

USER = {'id': '123e4567-e89b-12d3-a456-426614174000', 'email': 'redacted@example.com'}


class Step21SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.ChemiHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def request(self, path, method='GET', payload=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        body = json.dumps(payload).encode() if payload is not None else None
        hdr = {'X-CHEMI-Request': '1', 'Content-Type': 'application/json'}
        if headers:
            hdr.update(headers)
        connection.request(method, path, body=body, headers=hdr)
        response = connection.getresponse()
        code, all_headers, data = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return code, all_headers, json.loads(data) if 'application/json' in all_headers.get('Content-Type', '') else data

    def test_html_and_api_protection_headers(self):
        for path in ('/', '/api/health'):
            code, headers, _ = self.request(path)
            self.assertEqual(code, 200)
            self.assertEqual(headers['X-Frame-Options'], 'DENY')
            self.assertEqual(headers['Referrer-Policy'], 'no-referrer')
            self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(headers['Cache-Control'], 'no-store')

    def test_refresh_requires_login_when_cloud_enabled(self):
        with patch.object(cloud_store, 'configured', return_value=True), patch.object(contests, 'refresh') as refresh:
            status, _, body = self.request('/api/contests/refresh', 'POST')
            self.assertEqual(status, 401)
            self.assertIn('로그인', body['error'])
            refresh.assert_not_called()

    def test_refresh_accepts_logged_in_user(self):
        with patch.object(cloud_store, 'configured', return_value=True), \
             patch.object(cloud_store, 'verify_user', return_value=USER), \
             patch.object(contests, 'refresh', return_value={'items': [], 'updated_at': 'mock'}):
            status, _, data = self.request('/api/contests/refresh', 'POST', headers={'Cookie': 'chemi_access=testtoken'})
            self.assertEqual(status, 200)
            self.assertEqual(data['updated_at'], 'mock')

    def test_refresh_rejects_cross_origin(self):
        with patch.object(cloud_store, 'configured', return_value=True):
            status, _, _ = self.request('/api/contests/refresh', 'POST', headers={'Origin': 'https://other.example'})
            self.assertEqual(status, 403)

    def test_ai_limiter_denies_excess_for_user_only(self):
        limiter = server.UserHourlyLimiter(limit=2, window_seconds=60)
        self.assertTrue(limiter.allow('A', now=100))
        self.assertTrue(limiter.allow('A', now=101))
        self.assertFalse(limiter.allow('A', now=102))
        self.assertTrue(limiter.allow('B', now=102))
        self.assertTrue(limiter.allow('A', now=161))

    def test_ai_limit_returns_429_before_openai_call(self):
        limiter = server.UserHourlyLimiter(limit=1)
        with patch.object(server, '_ai_limiter', limiter):
            server.enforce_ai_budget(USER)
            with self.assertRaises(cloud_store.CloudError) as cm:
                server.enforce_ai_budget(USER)
            self.assertEqual(cm.exception.status, 429)

    def test_unauthenticated_ai_request_is_rejected_when_cloud_connected(self):
        with patch.object(cloud_store, 'configured', return_value=True), patch.object(server, 'call_openai') as upstream:
            status, _, _ = self.request('/api/interview/question', 'POST', {'stage': 1, 'initial_experience': '교내 개발 프로젝트'})
            self.assertEqual(status, 401)
            upstream.assert_not_called()

    def test_unconfigured_public_host_rejects_openai_proxy(self):
        with patch.object(cloud_store, 'configured', return_value=False), patch.object(server, 'HOST', '0.0.0.0'), \
             patch.object(server, 'call_openai') as upstream:
            status, _, _ = self.request('/api/interview/question', 'POST', {'stage': 1, 'initial_experience': '교내 개발 프로젝트'})
            self.assertEqual(status, 503)
            upstream.assert_not_called()

    def test_private_raw_experience_never_enters_matching_profile(self):
        from pathlib import Path
        sql = (Path(__file__).parent / 'matching_migration.sql').read_text(encoding='utf-8')
        self.assertIn('skill_names text[]', sql)
        self.assertNotIn('interview jsonb', sql)
        self.assertNotIn('email text', sql)
        self.assertIn('using ((select public.chemi_is_matching_member()))', sql)

    def test_environment_template_has_no_real_secrets(self):
        from pathlib import Path
        root = Path(__file__).parent
        self.assertIn('.env\n', (root / '.gitignore').read_text())
        example = (root / '.env.example').read_text()
        self.assertIn('sb_publishable_REPLACE_ME', example)
        self.assertNotIn('sk-proj-', example)


if __name__ == '__main__':
    unittest.main()
