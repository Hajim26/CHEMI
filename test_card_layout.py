"""Regression checks for teammate-card alignment and skill display."""
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

HTML=(Path(__file__).parent/'index.html').read_text(encoding='utf-8')

class CardLayoutTest(unittest.TestCase):
    def test_limited_two_skills(self):
        self.assertIn('skillNames.slice(0,2)',HTML)
        self.assertIn('skillNames.length-2',HTML)
    def test_fixed_reason_height_and_full_reason(self):
        self.assertIn('-webkit-line-clamp:2',HTML)
        self.assertIn('min-height:3.25em',HTML)
        self.assertIn('max-height:3.25em',HTML)
        self.assertIn('reason.title=reason.textContent',HTML)
    def test_bottom_centered_actions(self):
        self.assertIn('grid-column:1 / -1; grid-row:2',HTML)
        self.assertIn('justify-content:center',HTML)
        self.assertIn('strip.append(actionRow)',HTML)
        self.assertIn('strip.prepend(main,scoreBox)',HTML)
    def test_detail_and_invite_behaviors_preserved(self):
        self.assertIn('openMemberProfile(contest,teammateCache.get(key),detail)',HTML)
        self.assertIn('isRealInviteAllowed(data.member)',HTML)
        self.assertIn('sendMemberInvitation(data.member,contest,invite)',HTML)

if __name__=='__main__': unittest.main()
