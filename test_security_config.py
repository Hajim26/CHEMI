"""Static safety regression checks. Live RLS must also be tested in Supabase."""
from pathlib import Path
import unittest

ROOT=Path(__file__).parent

class TestSecurityConfiguration(unittest.TestCase):
    def test_only_opted_in_viewers_can_read_matching_profiles(self):
        sql=(ROOT/'matching_migration.sql').read_text(encoding='utf-8')
        self.assertIn('create or replace function public.chemi_is_matching_member()',sql)
        self.assertIn('for select to authenticated using ((select public.chemi_is_matching_member()))',sql)
        self.assertIn('revoke all on public.chemi_match_profiles from anon, authenticated',sql)
        self.assertIn('revoke all on public.chemi_match_requests from anon, authenticated',sql)
        self.assertNotIn('for select to authenticated using (true)',sql)

    def test_secrets_not_in_git(self):
        ignore=(ROOT/'.gitignore').read_text(encoding='utf-8')
        self.assertIn('\n.env\n',ignore)
        self.assertIn('data/teammates.db',ignore)

if __name__=='__main__':
    unittest.main()
