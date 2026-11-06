"""Simulate both parties accepting, declining and cancelling, no real Supabase requests."""
import unittest
from unittest.mock import patch
import cloud_store
import live_match
from test_step13_two_accounts import FakeSupabase, A, B, C

class Step16StatusWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.fake=FakeSupabase()
        self.network=patch.object(cloud_store,'request',side_effect=self.fake.handle)
        self.network.start()
        self.addCleanup(self.network.stop)
        for token in ('token-a','token-b','token-c'):
            uid={'token-a':A,'token-b':B,'token-c':C}[token]
            live_match.update_participation(uid,token,True,['AI·개발'])

    def test_received_declined_visible_to_both_and_not_accept_again(self):
        pending=live_match.send_request(A,'token-a',{
            'recipient_id':B,'contest_id':'challenge-1','contest_title':'AI 공모전','message':'협력 제안'})
        self.assertEqual(pending['status'],'pending')
        a=live_match.requests(A,'token-a')
        b=live_match.requests(B,'token-b')
        self.assertEqual(a[0]['direction'],'sent')
        self.assertEqual(b[0]['direction'],'received')
        declined=live_match.respond(B,'token-b',{'request_id':pending['id'],'action':'declined'})
        self.assertEqual(declined['status'],'declined')
        self.assertEqual(live_match.requests(A,'token-a')[0]['status'],'declined')
        with self.assertRaises(cloud_store.CloudError):
            live_match.respond(B,'token-b',{'request_id':pending['id'],'action':'accepted'})

    def test_sender_can_cancel_and_other_users_cannot_interfere(self):
        pending=live_match.send_request(A,'token-a',{
            'recipient_id':B,'contest_id':'challenge-2','contest_title':'디자인 공모전','message':''})
        with self.assertRaises(cloud_store.CloudError):
            live_match.respond(C,'token-c',{'request_id':pending['id'],'action':'accepted'})
        cancelled=live_match.respond(A,'token-a',{'request_id':pending['id'],'action':'cancelled'})
        self.assertEqual(cancelled['status'],'cancelled')
        self.assertEqual(live_match.requests(B,'token-b')[0]['status'],'cancelled')

    def test_acceptance_visible_to_both_without_private_contact(self):
        pending=live_match.send_request(A,'token-a',{
            'recipient_id':B,'contest_id':'challenge-3','contest_title':'지역 공모전','message':'함께해요'})
        live_match.respond(B,'token-b',{'request_id':pending['id'],'action':'accepted'})
        for uid,token in [(A,'token-a'),(B,'token-b')]:
            result=live_match.requests(uid,token)
            self.assertEqual(result[0]['status'],'accepted')
            self.assertNotIn('email',result[0])
            self.assertNotIn('phone',result[0])

if __name__=='__main__': unittest.main()
