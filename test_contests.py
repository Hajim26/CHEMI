"""No requests to public sites during tests: all external access mocked."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import contests
import server

PAGE = '''<html><table><tr><th>번호</th><th>캠퍼스</th><th>제목</th><th>등록일시</th><th>조회수</th></tr>
<tr><td>4221</td><td>춘천 삼척</td><td><a href="/ko/bbs/719/detail.do?pageIndex=1&amp;pstSn=4276">2026학년도 지역문제 기반 프로젝트 공모전 안내</a></td><td>2026.11.05</td><td>41</td></tr>
<tr><td>4220</td><td>ALL</td><td><a onclick="fnView('4275')">2026년 재난안전 AI 데이터 활용 해커톤</a></td><td>2026.11.02</td><td>30</td></tr></table></html>'''

class TestContestCollector(unittest.TestCase):
    def test_parser(self):
        result = contests.parse_list(PAGE)
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]['title'], '2026학년도 지역문제 기반 프로젝트 공모전 안내')
        self.assertEqual(result[1]['category'], 'AI·개발')
        self.assertEqual(result[0]['url'], 'https://www.kangwon.ac.kr/ko/bbs/719/detail.do?pstSn=4276')
        self.assertNotIn('deadline', result[0])

    def test_robots_denied_and_cache_retained(self):
        with tempfile.TemporaryDirectory() as d, patch.object(contests, 'CACHE', Path(d)/'contests.json'), patch.object(contests, 'CSV', Path(d)/'contests.csv'), patch.object(contests, 'DATA', Path(d)), patch.object(contests, 'LAST_ATTEMPT', 0), patch.object(contests, 'fetch', return_value='User-agent: *\nDisallow: /') as f:
            contests.save_cache([{'id':'old', 'title':'기존 공고'}])
            with self.assertRaises(contests.CrawlError): contests.refresh()
            self.assertEqual(contests.read_cache()['items'][0]['id'],'old')
            self.assertEqual(f.call_count,1)

    def test_success_updates_json_csv(self):
        def fake_fetch(url):
            return 'User-agent: *\nAllow: /ko/bbs/719/' if url.endswith('/robots.txt') else PAGE
        with tempfile.TemporaryDirectory() as d, patch.object(contests, 'CACHE', Path(d)/'contests.json'), patch.object(contests, 'CSV', Path(d)/'contests.csv'), patch.object(contests, 'DATA', Path(d)), patch.object(contests, 'LAST_ATTEMPT', 0), patch.object(contests, 'PAGES',1), patch.object(contests, 'fetch', side_effect=fake_fetch) as f:
            result=contests.refresh()
            self.assertEqual(len(result['items']),2)
            self.assertTrue(Path(d,'contests.csv').exists())
            self.assertEqual(contests.read_cache()['items'][0]['id'],'4276')
            self.assertEqual(f.call_count,2)

    @patch.object(server.cloud_store, 'configured', return_value=False)
    def test_http_refresh_endpoint(self, _configured):
        # This test mocks the collector, so it runs without a Supabase account.
        httpd=ThreadingHTTPServer(('127.0.0.1', 0), server.ChemiHandler)
        th=threading.Thread(target=httpd.serve_forever,daemon=True);th.start()
        try:
            conn=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
            conn.request('POST','/api/contests/refresh')
            r=conn.getresponse();r.read();self.assertEqual(r.status,403)
            conn.close()
            with patch.object(contests,'refresh',return_value={'items':[{'title':'실제 링크'}], 'updated_at':'2026-11-06T03:10:00+09:00'}):
                conn=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
                conn.request('POST','/api/contests/refresh',headers={'X-CHEMI-Request':'1'})
                r=conn.getresponse();raw=r.read();self.assertEqual(r.status,200)
                self.assertEqual(json.loads(raw)['items'][0]['title'],'실제 링크')
                conn.close()
        finally:
            httpd.shutdown(); httpd.server_close()

if __name__=='__main__':unittest.main()
