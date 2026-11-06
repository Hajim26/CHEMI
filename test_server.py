"""OpenAI 호출을 모의 응답으로 바꾸어 엔드포인트/검증을 테스트합니다.
실제 API 키 및 사용요금이 필요하지 않습니다.
실행: python -m unittest test_server.py -v
"""
import http.client
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import server


class MockOpenAI:
    def __init__(self):
        self.requests = []

    def __call__(self, req, timeout=55):
        assert req.full_url == 'https://api.openai.com/v1/responses'
        body = json.loads(req.data.decode('utf-8'))
        self.requests.append(body)
        if 'question' in body['text']['format']['name']:
            question = '어떤 부분을 직접 담당했나요?' if 'question_1' in body['text']['format']['name'] else '두 번째 활동에서는 어떤 일을 직접 하셨나요?'
            result = {'question': question}
        else:
            result = {'summary': '프로젝트에서 데이터 정리를 경험했어요.',
                      'competencies': [{'name':'데이터 처리', 'evidence':'Python으로 데이터 전처리를 맡았다고 서술했어요.', 'evidence_level':'명확'}],
                      'caution': '예비 분석'}

        class Reply:
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def read(self):
                text = json.dumps(result, ensure_ascii=False)
                return json.dumps({'output':[{'type':'message','content':[{'type':'output_text','text':text}]}]},ensure_ascii=False).encode()
        return Reply()


class TestChemiInterview(unittest.TestCase):
    def setUp(self):
        # These legacy endpoint unit tests deliberately exercise the no-Supabase,
        # localhost interview flow. A developer's .env must not change their behavior.
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
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def req(self, path, data=None, method='POST'):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        body = None if data is None else json.dumps(data,ensure_ascii=False).encode('utf-8')
        headers = {'Content-Type':'application/json', 'X-CHEMI-Request':'1'} if body else {}
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        output = resp.read()
        conn.close()
        return resp.status, json.loads(output.decode('utf-8')) if 'json' in resp.getheader('Content-Type','') else output

    def test_health_and_page(self):
        status, page = self.req('/', method='GET')
        self.assertEqual(status, 200)
        self.assertIn('새로운 경험이나 활동이 있나요?'.encode('utf-8'), page)
        # URLs copied from ChatGPT can include tracking query parameters.
        status_with_query, page_with_query = self.req('/?utm_source=chatgpt.com', method='GET')
        self.assertEqual(status_with_query, 200)
        self.assertEqual(page_with_query, page)
        self.assertEqual(self.req('/index.html?utm_source=chatgpt.com', method='GET')[0], 200)
        status, data = self.req('/api/health', method='GET')
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])

    def test_competency_to_contest_markup(self):
        status, page = self.req('/', method='GET')
        self.assertEqual(status, 200)
        doc = page.decode('utf-8')
        for s in ('id="finishCompetencyBtn"', 'id="screenContest"', 'id="contestGrid"', '핵심역량 완료', '샘플 공모전'):
            self.assertIn(s, doc)

    def test_invalid_payloads(self):
        self.assertEqual(self.req('/api/interview/question',{'stage':4,'initial_experience':'코딩'})[0],400)
        self.assertEqual(self.req('/api/interview/question',{'stage':1,'initial_experience':' '})[0],400)
        self.assertEqual(self.req('/api/interview/question',{'stage':2,'initial_experience':'코딩'})[0],400)
        self.assertEqual(self.req('/api/interview/analyze',{'initial_experience':'코딩','first_question':'어떤 역할?','first_answer':'개발', 'additional_experience':'디자인'})[0],400)
        self.assertEqual(self.req('/api/interview/question',{'stage':1,'initial_experience':'가'*4001})[0],400)

    def test_missing_key(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
            code, response = self.req('/api/interview/question',{'stage':1,'initial_experience':'데이터 정리'})
            self.assertEqual(code,503)
            self.assertIn('OPENAI_API_KEY',response['error'])

    def test_two_questions_then_analysis(self):
        mock = MockOpenAI()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-test-not-real'}), patch.object(server,'urlopen',mock):
            data1={'stage':1,'initial_experience':'Python으로 CSV 데이터 전처리를 수행했어요.'}
            code,q1=self.req('/api/interview/question',data1)
            self.assertEqual(code,200)
            self.assertEqual(q1['stage'],1)
            data2={**data1,'stage':2,'first_question':q1['question'], 'first_answer':'제가 이상치를 정리했어요.', 'additional_experience':'동아리에서 홍보 포스터 제작'}
            code,q2=self.req('/api/interview/question',data2)
            self.assertEqual(code,200)
            self.assertEqual(q2['stage'],2)
            all_data={k:v for k,v in data2.items() if k!='stage'}
            all_data.update({'second_question':q2['question'],'second_answer':'시안을 직접 만들었어요.'})
            code,result=self.req('/api/interview/analyze',all_data)
            self.assertEqual(code,200)
            self.assertEqual(result['competencies'][0]['name'],'데이터 처리')
            self.assertEqual(len(mock.requests),3)
            self.assertTrue(all(p['store'] is False for p in mock.requests))
            self.assertEqual(all(p['model']==server.MODEL for p in mock.requests),True)
            for p in mock.requests:
                request_text = str(p['input'])
                self.assertNotIn('user@example', request_text)
                self.assertNotIn('학과 이름',request_text)
                self.assertNotIn('sk-test-not-real',request_text)

    def test_skip_additional_experience(self):
        mock = MockOpenAI()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-test-not-real'}), patch.object(server,'urlopen',mock):
            payload={'initial_experience':'학생식당 앱 기획', 'first_question':'어떤 일을?','first_answer':'기능을 기획했어요.', 'additional_experience':'', 'second_question':'', 'second_answer':''}
            code,result=self.req('/api/interview/analyze',payload)
            self.assertEqual(code,200)
            self.assertEqual(len(mock.requests),1)
            self.assertIn('competencies',result)


if __name__=='__main__':
    unittest.main()
