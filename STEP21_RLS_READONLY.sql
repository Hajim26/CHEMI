-- CHEMI 단계 21: read-only Supabase permission audit.
-- Run in SQL Editor; this file does NOT change or delete data.
-- 1) Both private tables and both matching tables must have RLS enabled.
select c.relname as table_name, c.relrowsecurity as rls_enabled
from pg_catalog.pg_class c
join pg_catalog.pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public'
  and c.relname in ('chemi_profiles','chemi_analyses','chemi_match_profiles','chemi_match_requests')
order by c.relname;

-- 2) Inspect each current RLS policy. Private-table SELECT should restrict auth.uid() = user_id.
--    Matching profiles must restrict SELECT to opted-in viewers.
--    Match requests SELECT should allow only sender_id or recipient_id.
select tablename, policyname, cmd, roles, qual, with_check
from pg_catalog.pg_policies
where schemaname='public'
  and tablename in ('chemi_profiles','chemi_analyses','chemi_match_profiles','chemi_match_requests')
order by tablename, policyname;

-- 3) Inspect direct grants. Anonymous clients must not be able to read personal data.
select table_name, grantee, privilege_type
from information_schema.role_table_grants
where table_schema='public'
  and table_name in ('chemi_profiles','chemi_analyses','chemi_match_profiles','chemi_match_requests')
  and grantee in ('anon', 'authenticated')
order by table_name, grantee, privilege_type;
