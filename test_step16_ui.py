"""Step 16 UI tests: request states, tab separation and privacy boundaries."""
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

HTML=(Path(__file__).parent/'index.html').read_text(encoding='utf-8')
DOM=BeautifulSoup(HTML,'html.parser')
SCRIPT=DOM.script.string

class Step16RequestUITest(unittest.TestCase):
    def test_request_panel_has_separate_tabs_and_status_summary(self):
        for element in ('receivedRequestsTab','sentRequestsTab','receivedRequestsCount','sentRequestsCount',
                        'requestPendingReceived','requestPendingSent','requestAcceptedTotal','matchRequestFeedback'):
            self.assertIsNotNone(DOM.select_one('#'+element),element)
        self.assertEqual(DOM.select_one('#receivedRequestsTab')['aria-pressed'],'true')
        self.assertEqual(DOM.select_one('#sentRequestsTab')['aria-pressed'],'false')

    def test_request_actions_are_limited_to_allowed_directions_and_pending(self):
        self.assertIn("record.status==='pending'",SCRIPT)
        self.assertIn("record.direction==='received'?[['accepted','수락'],['declined','거절']]:[['cancelled','요청 취소']]",SCRIPT)
        self.assertIn("await apiCall('/api/team/respond','POST',{request_id:record.id,action})",SCRIPT)
        for status in ('pending','accepted','declined','cancelled'):
            self.assertIn(status,SCRIPT)
        self.assertIn('requestStatusLabels',SCRIPT)

    def test_privacy_and_no_fake_team_completion(self):
        self.assertIn('이메일·연락처는 자동 공개되지 않아요.',SCRIPT)
        self.assertNotIn('팀 구성이 자동 완료',SCRIPT)
        self.assertIn('record.message',SCRIPT)
        self.assertIn('textContent=`요청 메시지:',SCRIPT)

    def test_compact_card_and_two_skills_preserved(self):
        self.assertIn('min-height:186px',HTML)
        self.assertIn('skillNames.slice(0,2)',HTML)
        self.assertIn('skillNames.length-2',HTML)
        self.assertIn("scoreLabel.textContent='궁합 점수'",SCRIPT)

if __name__=='__main__':unittest.main()
