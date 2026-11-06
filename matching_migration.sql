-- CHEMI step 11. Run AFTER database_setup.sql in Supabase SQL Editor.
-- Private experience text, email and analysis evidence NEVER enter the matchmaking table.
-- Do not use a service_role key in the CHEMI application.

create table if not exists public.chemi_match_profiles (
    user_id uuid primary key references public.chemi_profiles(user_id) on delete cascade,
    nickname text not null check (length(nickname) between 1 and 24),
    major text not null check (length(major) between 1 and 70),
    skill_names text[] not null default '{}'::text[] check (cardinality(skill_names) between 1 and 5),
    interests text[] not null default '{}'::text[] check (cardinality(interests) <= 5),
    opted_in_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create table if not exists public.chemi_match_requests (
    id bigint generated always as identity primary key,
    sender_id uuid not null references public.chemi_match_profiles(user_id) on delete cascade,
    recipient_id uuid not null references public.chemi_match_profiles(user_id) on delete cascade,
    contest_id text not null check (length(contest_id) between 1 and 350),
    contest_title text not null check (length(contest_title) between 1 and 260),
    message text not null default '' check (length(message) <= 160),
    status text not null default 'pending' check (status in ('pending','accepted','declined','cancelled')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (sender_id <> recipient_id),
    unique(sender_id, recipient_id, contest_id)
);
create index if not exists chemi_requests_sender_idx on public.chemi_match_requests(sender_id,created_at desc);
create index if not exists chemi_requests_recipient_idx on public.chemi_match_requests(recipient_id,created_at desc);

alter table public.chemi_match_profiles enable row level security;
alter table public.chemi_match_requests enable row level security;
revoke all on public.chemi_match_profiles from anon, authenticated;
revoke all on public.chemi_match_requests from anon, authenticated;
grant select on public.chemi_match_profiles to authenticated;
grant select on public.chemi_match_requests to authenticated;

-- Reading candidates also requires the *viewer* to opt in, not merely to be logged in.
-- SECURITY DEFINER prevents recursive RLS lookup while checking this membership.
-- This function does not return other users' data.
create or replace function public.chemi_is_matching_member()
returns boolean language sql stable security definer set search_path = '' as $$
    select (select auth.uid()) is not null and exists (
      select 1 from public.chemi_match_profiles
      where user_id = (select auth.uid())
    );
$$;
revoke all on function public.chemi_is_matching_member() from public, anon;
grant execute on function public.chemi_is_matching_member() to authenticated;

drop policy if exists chemi_match_profiles_opted_in_read on public.chemi_match_profiles;
create policy chemi_match_profiles_opted_in_read on public.chemi_match_profiles
    for select to authenticated using ((select public.chemi_is_matching_member()));
drop policy if exists chemi_match_requests_participants on public.chemi_match_requests;
create policy chemi_match_requests_participants on public.chemi_match_requests
    for select to authenticated using ((select auth.uid()) in (sender_id,recipient_id));

-- Only the server-verified user's own PRIVATE records may be copied to public matching profile.
-- Function runs as creator, so set search_path = '' and schema-qualify relations.
create or replace function public.chemi_set_match_visibility(p_enabled boolean, p_interests text[] default '{}'::text[])
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
    v_uid uuid := (select auth.uid());
    v_profile public.chemi_profiles%rowtype;
    v_skills text[];
    v_interests text[];
begin
    if v_uid is null then raise exception '로그인이 필요합니다.'; end if;
    if not coalesce(p_enabled, false) then
        delete from public.chemi_match_profiles where user_id = v_uid;
        return jsonb_build_object('enabled',false);
    end if;
    select * into v_profile from public.chemi_profiles where user_id=v_uid;
    if not found then raise exception '기본 프로필을 먼저 저장하세요.'; end if;
    select coalesce(array_agg(skill_name), '{}'::text[]) into v_skills
    from (select left(btrim(item->>'name'), 70) as skill_name
          from public.chemi_analyses a cross join lateral jsonb_array_elements(a.competencies) item
          where a.user_id=v_uid and jsonb_typeof(item)='object' and length(btrim(item->>'name')) > 0
          limit 5) s;
    if cardinality(v_skills)=0 then raise exception 'AI 핵심역량 분석을 먼저 완료하세요.'; end if;
    select coalesce(array_agg(left(btrim(t), 30)), '{}'::text[]) into v_interests
      from (select distinct t from unnest(coalesce(p_interests,'{}'::text[])) as t
            where length(btrim(t)) between 1 and 30 limit 5) i;
    insert into public.chemi_match_profiles(user_id,nickname,major,skill_names,interests)
       values(v_uid,v_profile.nickname,v_profile.major,v_skills,v_interests)
    on conflict (user_id) do update set nickname=excluded.nickname,major=excluded.major,
        skill_names=excluded.skill_names,interests=excluded.interests,updated_at=now();
    return jsonb_build_object('enabled',true,'nickname',v_profile.nickname,'skills',v_skills,'interests',v_interests);
end $$;

-- If the user changes the private analysis, refresh the public skill names without exposing evidence.
create or replace function public.chemi_sync_matching_analysis()
returns trigger language plpgsql security definer set search_path = '' as $$
declare v_skills text[];
begin
    select coalesce(array_agg(skill_name), '{}'::text[]) into v_skills
    from (select left(btrim(item->>'name'),70) as skill_name
          from jsonb_array_elements(new.competencies) item
          where jsonb_typeof(item)='object' and length(btrim(item->>'name'))>0 limit 5) s;
    if cardinality(v_skills)>0 then
        update public.chemi_match_profiles set skill_names=v_skills,updated_at=now() where user_id=new.user_id;
    else
        delete from public.chemi_match_profiles where user_id=new.user_id;
    end if;
    return new;
end $$;
drop trigger if exists chemi_sync_matching_analysis on public.chemi_analyses;
create trigger chemi_sync_matching_analysis after insert or update of competencies on public.chemi_analyses
    for each row execute function public.chemi_sync_matching_analysis();

create or replace function public.chemi_sync_matching_profile()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
    update public.chemi_match_profiles set nickname=new.nickname,major=new.major,updated_at=now() where user_id=new.user_id;
    return new;
end $$;
drop trigger if exists chemi_sync_matching_profile on public.chemi_profiles;
create trigger chemi_sync_matching_profile after update of nickname,major on public.chemi_profiles
    for each row execute function public.chemi_sync_matching_profile();

-- Requests are exclusively created by this RPC. Client cannot directly insert into requests.
create or replace function public.chemi_send_match_request(p_recipient uuid, p_contest_id text, p_contest_title text, p_message text default '')
returns jsonb language plpgsql security definer set search_path = '' as $$
declare v_uid uuid := (select auth.uid()); v_id bigint;
begin
    if v_uid is null then raise exception '로그인이 필요합니다.'; end if;
    if v_uid=p_recipient then raise exception '자신에게 매칭 요청을 보낼 수 없습니다.'; end if;
    if not exists(select 1 from public.chemi_match_profiles where user_id=v_uid) then
        raise exception '팀원 매칭 참여에 동의해야 요청할 수 있습니다.';
    end if;
    if not exists(select 1 from public.chemi_match_profiles where user_id=p_recipient) then
        raise exception '상대방이 현재 매칭에 참여하지 않습니다.';
    end if;
    if length(btrim(coalesce(p_contest_id,''))) not between 1 and 350
       or length(btrim(coalesce(p_contest_title,''))) not between 1 and 260
       or length(coalesce(p_message,''))>160 then raise exception '요청 정보를 확인하세요.'; end if;
    if (select count(*) from public.chemi_match_requests
        where sender_id=v_uid and created_at > now()-interval '24 hours') >= 5 then
        raise exception '매칭 요청은 24시간에 5개까지 보낼 수 있습니다.';
    end if;
    insert into public.chemi_match_requests(sender_id,recipient_id,contest_id,contest_title,message)
        values(v_uid,p_recipient,btrim(p_contest_id),btrim(p_contest_title),coalesce(p_message,''))
        on conflict (sender_id,recipient_id,contest_id) do nothing returning id into v_id;
    if v_id is null then raise exception '해당 팀원에게 이미 이 공모전의 요청을 보냈습니다.'; end if;
    return jsonb_build_object('id',v_id,'status','pending');
end $$;

create or replace function public.chemi_respond_match_request(p_request_id bigint, p_action text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare v_uid uuid := (select auth.uid()); v_record public.chemi_match_requests%rowtype;
begin
    if v_uid is null then raise exception '로그인이 필요합니다.'; end if;
    select * into v_record from public.chemi_match_requests where id=p_request_id for update;
    if not found then raise exception '해당 요청이 존재하지 않습니다.'; end if;
    if v_record.status <> 'pending' then raise exception '이미 처리된 요청입니다.'; end if;
    if (p_action in ('accepted','declined') and v_uid=v_record.recipient_id)
       or (p_action='cancelled' and v_uid=v_record.sender_id) then
        update public.chemi_match_requests set status=p_action,updated_at=now() where id=p_request_id;
        return jsonb_build_object('id',p_request_id,'status',p_action);
    end if;
    raise exception '이 요청을 처리할 권한이 없습니다.';
end $$;

revoke all on function public.chemi_set_match_visibility(boolean,text[]) from public, anon;
revoke all on function public.chemi_send_match_request(uuid,text,text,text) from public, anon;
revoke all on function public.chemi_respond_match_request(bigint,text) from public, anon;
grant execute on function public.chemi_set_match_visibility(boolean,text[]) to authenticated;
grant execute on function public.chemi_send_match_request(uuid,text,text,text) to authenticated;
grant execute on function public.chemi_respond_match_request(bigint,text) to authenticated;

-- Validate public access: anon has no SELECT and authenticated has no direct write.
-- Only after explicit opt-in will users appear in chemi_match_profiles.
