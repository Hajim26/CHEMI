-- CHEMI step 9: Supabase SQL Editor에서 한 번 실행합니다.
-- 실제 사용자 계정은 Supabase Auth(auth.users), 개인정보는 아래 소유자 전용 테이블에 저장됩니다.
-- 가상 10명 SQLite DB와는 분리됩니다. 공개 매칭용 테이블은 아직 만들지 않습니다.
create table if not exists public.chemi_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  nickname text not null check (length(nickname) between 1 and 24),
  university text not null check (length(university) between 1 and 60),
  major text not null check (length(major) between 1 and 70),
  grade text not null check (grade in ('1학년','2학년','3학년','4학년','5학년 이상','휴학생','졸업생')),
  consent_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.chemi_analyses (
  user_id uuid primary key references public.chemi_profiles(user_id) on delete cascade,
  interview jsonb not null check (jsonb_typeof(interview) = 'object'),
  summary text not null,
  competencies jsonb not null check (jsonb_typeof(competencies) = 'array'),
  caution text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function public.chemi_touch_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists chemi_profiles_touch on public.chemi_profiles;
create trigger chemi_profiles_touch before update on public.chemi_profiles
for each row execute function public.chemi_touch_updated_at();
drop trigger if exists chemi_analyses_touch on public.chemi_analyses;
create trigger chemi_analyses_touch before update on public.chemi_analyses
for each row execute function public.chemi_touch_updated_at();

alter table public.chemi_profiles enable row level security;
alter table public.chemi_analyses enable row level security;
revoke all on public.chemi_profiles from anon, authenticated;
revoke all on public.chemi_analyses from anon, authenticated;
grant select, insert, update, delete on public.chemi_profiles to authenticated;
grant select, insert, update, delete on public.chemi_analyses to authenticated;

-- 재실행 시 중복 정책 생성 방지
drop policy if exists chemi_profile_read_self on public.chemi_profiles;
drop policy if exists chemi_profile_insert_self on public.chemi_profiles;
drop policy if exists chemi_profile_update_self on public.chemi_profiles;
drop policy if exists chemi_profile_delete_self on public.chemi_profiles;
create policy chemi_profile_read_self on public.chemi_profiles for select to authenticated
using ((select auth.uid()) = user_id);
create policy chemi_profile_insert_self on public.chemi_profiles for insert to authenticated
with check ((select auth.uid()) = user_id);
create policy chemi_profile_update_self on public.chemi_profiles for update to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy chemi_profile_delete_self on public.chemi_profiles for delete to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists chemi_analysis_read_self on public.chemi_analyses;
drop policy if exists chemi_analysis_insert_self on public.chemi_analyses;
drop policy if exists chemi_analysis_update_self on public.chemi_analyses;
drop policy if exists chemi_analysis_delete_self on public.chemi_analyses;
create policy chemi_analysis_read_self on public.chemi_analyses for select to authenticated
using ((select auth.uid()) = user_id);
create policy chemi_analysis_insert_self on public.chemi_analyses for insert to authenticated
with check ((select auth.uid()) = user_id);
create policy chemi_analysis_update_self on public.chemi_analyses for update to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy chemi_analysis_delete_self on public.chemi_analyses for delete to authenticated
using ((select auth.uid()) = user_id);

-- anon 역할은 프로필과 역량에 대한 권한이 없어야 합니다.
-- 사용자끼리의 공개 매칭이 필요할 때 별도 공개용 프로필 + 동의 정책을 설계하세요.
