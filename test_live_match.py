"""No real Supabase/OpenAI calls: validates privacy and API contracts for matching MVP."""
import http.client
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import server
import cloud_store
import live_match

UID_A='123e4567-e89b-12d3-a456-426614174000'
UID_B='123e4567-e89b-12d3-a456-426614174001'


class TestRealMatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv=ThreadingHTTPServer(('127.0.0.1',0),server.ChemiHandler)
        cls.thread=threading.Thread(target=cls.srv.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown();cls.srv.server_close()

    def request(self,method,path,payload=None,authenticated=True):
        cn=http.client.HTTPConnection('127.0.0.1',self.srv.server_port,timeout=5)
        headers={'Content-Type':'application/json','X-CHEMI-Request':'1'}
        if authenticated: headers['Cookie']='chemi_access=test-token'
        raw=json.dumps(payload).encode() if payload is not None else None
        cn.request(method,path,raw,headers)
        res=cn.getresponse();data=json.loads(res.read());status=res.status;cn.close()
        return status,data

    def test_no_anonymous_matching_requests(self):
        with patch.object(cloud_store,'configured',return_value=True):
            s,_=self.request('GET','/api/me/matching',authenticated=False)
            self.assertEqual(s,401)
            s,_=self.request('POST','/api/team/request',{'recipient_id':UID_B,'contest_id':'one','contest_title':'시험'},authenticated=False)
            self.assertEqual(s,401)

    def test_consent_write_uses_authenticated_identity(self):
        with patch.object(cloud_store,'configured',return_value=True),\
             patch.object(cloud_store,'verify_user',return_value={'id':UID_A,'email':'a@example.com'}),\
             patch.object(live_match,'update_participation',return_value={'enabled':True}) as update:
            s,d=self.request('POST','/api/me/matching',{'enabled':True,'interests':['디자인'],'user_id':UID_B})
            self.assertEqual(s,200);self.assertTrue(d['result']['enabled'])
            self.assertEqual(update.call_args.args[:2],(UID_A,'test-token'))
            self.assertEqual(update.call_args.args[2:4],(True,['디자인']))

    def test_candidate_uses_only_public_attributes_and_not_self(self):
        public=[{'user_id':UID_A,'nickname':'나','major':'개발','skill_names':['Python'],'interests':[]},
                {'user_id':UID_B,'nickname':'가상 아님','major':'디자인학과','skill_names':['UI 디자인','Figma'], 'interests':['디자인'],'email':'NOT_ALLOWED','interview':'PRIVATE'}]
        with patch.object(live_match,'my_participation',return_value={'enabled':True}), \
             patch.object(cloud_store,'request',return_value=public):
            candidates=live_match.candidates(UID_A,'test-token')
        self.assertEqual(len(candidates),1)
        self.assertEqual(candidates[0]['id'],UID_B)
        self.assertFalse(candidates[0]['is_synthetic'])
        self.assertNotIn('email',candidates[0])
        self.assertNotIn('interview',candidates[0])

    def test_real_candidate_match_uses_saved_analysis_not_browser_data(self):
        members=[{'id':UID_B,'nickname':'학생 B','major':'디자인학과','skills':[{'name':'UI 디자인','category':'디자인'}],
                  'interests':['디자인'],'is_synthetic':False}]
        payload={'competencies':[{'name':'공격자 주입 역량','evidence':'가짜','evidence_level':'명확'}],
                 'contests':[{'id':'contest-1','title':'디자인 공모전','category':'디자인'}], 'mode':'estimate'}
        with patch.object(cloud_store,'configured',return_value=True),\
             patch.object(cloud_store,'verify_user',return_value={'id':UID_A,'email':'a@example.com'}),\
             patch.object(cloud_store,'fetch_analysis',return_value={'competencies':[{'name':'Python 프로그래밍','evidence':'팀 개발','evidence_level':'명확'}]}),\
             patch.object(live_match,'my_participation',return_value={'enabled':True}),\
             patch.object(live_match,'candidates',return_value=members):
            status,data=self.request('POST','/api/team/match',payload)
        self.assertEqual(status,200)
        self.assertFalse(data['synthetic'])
        self.assertEqual(data['real_candidate_count'],1)
        self.assertEqual(data['matches'][0]['member']['id'],UID_B)
        self.assertNotIn('email',data['matches'][0]['member'])

    def test_no_real_members_with_public_fallback_disabled(self):
        payload={'competencies':[{'name':'Python 개발','evidence':'직접 구현'}],
                 'contests':[{'id':'one','title':'AI 개발','category':'AI·개발'}]}
        with patch.dict(os.environ, {'CHEMI_ALLOW_DEMO_FALLBACK':'0'}),\
             patch.object(cloud_store,'configured',return_value=True),\
             patch.object(cloud_store,'verify_user',return_value={'id':UID_A,'email':'a@example.com'}),\
             patch.object(cloud_store,'fetch_analysis',return_value={'competencies':payload['competencies']}),\
             patch.object(live_match,'my_participation',return_value={'enabled':True}),\
             patch.object(live_match,'candidates',return_value=[]):
            status,data=self.request('POST','/api/team/match',payload)
        self.assertEqual(status,200)
        self.assertEqual(data['matches'],[])
        self.assertEqual(data['real_candidate_count'],0)

    def test_receive_request_authorization_is_database_function(self):
        with patch.object(cloud_store,'configured',return_value=True),\
             patch.object(cloud_store,'verify_user',return_value={'id':UID_A,'email':'a@example.com'}),\
             patch.object(live_match,'respond',return_value={'status':'accepted'}) as fn:
            s,data=self.request('POST','/api/team/respond',{'request_id':1,'action':'accepted'})
            self.assertEqual(s,200)
            self.assertEqual(fn.call_args.args[0],UID_A)
            self.assertEqual(data['result']['status'],'accepted')

    def test_request_validation_rejects_oversize_and_unknown_action(self):
        with self.assertRaises(cloud_store.CloudError):
            live_match.send_request(UID_A,'token',{'recipient_id':UID_B,'contest_id':'x', 'contest_title':'test','message':'a'*200})
        with self.assertRaises(cloud_store.CloudError):
            live_match.respond(UID_A,'token',{'request_id':5,'action':'transfer_money'})


if __name__=='__main__':unittest.main()
