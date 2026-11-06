"""Safety and integration checks for new Step 14 teammate profile UI.

The interactive browser remains a separate final E2E test with user's Supabase.
"""
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
from team_database import get_members
from live_match import member_from_row

ROOT=Path(__file__).parent

class DetailUITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(ROOT/'index.html').read_text(encoding='utf-8')
        cls.dom=BeautifulSoup(cls.html,'html.parser')
        cls.script=cls.dom.script.string
    def test_modal_has_accessible_controls_and_privacy_notice(self):
        overlay=self.dom.select_one('#memberProfileOverlay')
        self.assertTrue(overlay.has_attr('hidden'))
        dialog=overlay.select_one('[role="dialog"][aria-modal="true"]')
        self.assertIsNotNone(dialog)
        for id in ('memberDialogClose','memberDialogBack','memberDialogInvite','memberDialogReason',
                   'memberDialogTheirSkills','memberDialogMySkills','memberDialogInterests','memberDialogScore',
                   'memberDialogMessage','memberDialogCaution','memberDialogInviteStatus'):
            self.assertIsNotNone(self.dom.select_one('#'+id), id)
        self.assertIn('경험 원문',self.dom.select_one('#memberDialogCaution').text)
    def test_candidate_click_and_invite_gates(self):
        self.assertIn('팀원 상세 보기 ↗',self.script)
        self.assertIn('openMemberProfile(contest,teammateCache.get(key),detail)',self.script)
        self.assertIn('!member.is_synthetic && actualMatchEnabled && cloudMode && signedIn && !previewMode',self.script)
        self.assertIn("data?.member && isRealInviteAllowed(data.member)",self.script)
        self.assertIn('sendMemberInvitation',self.script)
    def test_synthetic_records_are_realistic_but_marked(self):
        members=get_members()
        self.assertEqual(len(members),100)
        self.assertTrue(all(m['is_synthetic'] for m in members))
        self.assertTrue(all('email' not in m for m in members))
    def test_live_candidate_excludes_private_fields(self):
        raw={'user_id':'someuuid','nickname':'시연회원','major':'컴퓨터공학','skill_names':['Python','DB'],
             'interests':['AI·개발'],'email':'SECRET','summary':'PRIVATE','experience':'PRIVATE'}
        member=member_from_row(raw)
        self.assertEqual(set(member),{'id','nickname','major','skills','interests','is_synthetic'})
        self.assertFalse(member['is_synthetic'])

if __name__=='__main__':unittest.main()
