"""Opt-in matching and request workflow. All calls use the logged-in user's JWT + RLS.
Only public matching fields (nickname, major, skill names, interests) are retrieved.
"""
import re
from urllib.parse import urlencode

import cloud_store
from matchmaking import CATEGORIES

FIELDS = 'user_id,nickname,major,skill_names,interests,opted_in_at'
REQUEST_FIELDS = 'id,sender_id,recipient_id,contest_id,contest_title,message,status,created_at'


def _category(name):
    lower = name.lower()
    for domain, terms in CATEGORIES.items():
        if any(term in lower for term in terms):
            return domain
    return '기획·아이디어' if any(x in lower for x in ('소통', '팀워크', '협업')) else '기타'


def member_from_row(row):
    # Do not pass a real user's email, experience, evidence, or private summary.
    return {'id': row['user_id'], 'nickname': row['nickname'],
            'major': row['major'],
            'skills': [{'name': s, 'category': _category(s)} for s in row.get('skill_names', [])][:5],
            'interests': row.get('interests', []), 'is_synthetic': False}


def my_participation(uid, token):
    query = urlencode({'user_id': 'eq.' + uid, 'select': FIELDS, 'limit':'1'})
    rows = cloud_store.request('GET', '/rest/v1/chemi_match_profiles?' + query, token=token)
    if not isinstance(rows, list) or not rows:
        return {'enabled': False, 'interests': []}
    return {'enabled': True, 'interests': rows[0].get('interests', []),
            'skills': rows[0].get('skill_names', [])}


def update_participation(uid, token, enabled, interests):
    if type(enabled) is not bool:
        raise cloud_store.CloudError('매칭 참여 여부를 선택해 주세요.', 400)
    if not isinstance(interests, list) or len(interests) > 5 or any(
            not isinstance(x, str) or len(x.strip()) > 30 for x in interests):
        raise cloud_store.CloudError('관심 분야는 5개까지 입력할 수 있어요.', 400)
    # PostgreSQL function uses auth.uid() and re-reads private rows; it never trusts skills from browser.
    result = cloud_store.request('POST', '/rest/v1/rpc/chemi_set_match_visibility',
                                 {'p_enabled': enabled, 'p_interests': [x.strip() for x in interests if x.strip()]},
                                 token=token)
    return result if isinstance(result, dict) else {'enabled': enabled}


def candidates(uid, token, *, limit=400):
    if not my_participation(uid, token)['enabled']:
        return []
    query = urlencode({'select': FIELDS, 'user_id': 'neq.' + uid, 'limit': str(limit)})
    rows = cloud_store.request('GET', '/rest/v1/chemi_match_profiles?' + query, token=token)
    return [member_from_row(row) for row in rows if row.get('user_id') != uid] if isinstance(rows, list) else []


def requests(uid, token):
    # RLS enforces that only sender or recipient can see a given request.
    query = urlencode({'or': f'(sender_id.eq.{uid},recipient_id.eq.{uid})',
                       'select': REQUEST_FIELDS, 'order':'created_at.desc', 'limit':'100'})
    rows = cloud_store.request('GET', '/rest/v1/chemi_match_requests?' + query, token=token)
    # Nicknames are fetched from opt-in profiles only; never from private user records.
    public_rows = cloud_store.request('GET', '/rest/v1/chemi_match_profiles?' + urlencode({'select':'user_id,nickname','limit':'500'}), token=token)
    name_by_id = {r['user_id']: r['nickname'] for r in (public_rows or [])}
    return [{**r, 'direction': 'sent' if r['sender_id'] == uid else 'received',
             'other_nickname': name_by_id.get(r['recipient_id'] if r['sender_id'] == uid else r['sender_id'], '비공개 회원')}
            for r in (rows or [])]


def diagnostics(uid, token):
    """Read-only checks for a signed-in user, constrained by existing Supabase RLS.

    Counts are about opted-in profiles visible to this user, not all registered users.
    No names, user IDs, emails, experience text or matching evidence is returned.
    """
    mine = my_participation(uid, token)
    participating = bool(mine.get('enabled'))
    others = candidates(uid, token, limit=400) if participating else []
    rows = requests(uid, token)
    counts = {
        'sent': sum(r.get('direction') == 'sent' for r in rows),
        'received': sum(r.get('direction') == 'received' for r in rows),
        'pending_sent': sum(r.get('direction') == 'sent' and r.get('status') == 'pending' for r in rows),
        'pending_received': sum(r.get('direction') == 'received' and r.get('status') == 'pending' for r in rows),
        'accepted': sum(r.get('status') == 'accepted' for r in rows),
    }
    return {
        'participating': participating,
        'other_candidate_count': len(others),
        'other_candidate_count_capped': len(others) >= 400,
        'request_counts': counts,
    }

def send_request(uid, token, body):
    target = body.get('recipient_id', '')
    if not isinstance(target, str) or not re.fullmatch(r'[a-fA-F0-9-]{36}', target):
        raise cloud_store.CloudError('요청할 회원을 선택해 주세요.', 400)
    contest_id = body.get('contest_id', '')
    title = body.get('contest_title', '')
    message = body.get('message', '')
    if not isinstance(contest_id,str) or not 1 <= len(contest_id) <= 350 or not isinstance(title,str) or not 1 <= len(title) <= 260 or not isinstance(message,str) or len(message) > 160:
        raise cloud_store.CloudError('공모전과 요청 메시지를 확인해 주세요.', 400)
    return cloud_store.request('POST', '/rest/v1/rpc/chemi_send_match_request',
                              {'p_recipient': target, 'p_contest_id': contest_id,
                               'p_contest_title': title, 'p_message': message}, token=token)


def respond(uid, token, body):
    id_value = body.get('request_id')
    action = body.get('action')
    if type(id_value) is not int or id_value <= 0 or action not in ('accepted', 'declined', 'cancelled'):
        raise cloud_store.CloudError('요청 번호와 처리 방식을 확인해 주세요.', 400)
    return cloud_store.request('POST', '/rest/v1/rpc/chemi_respond_match_request',
                              {'p_request_id': id_value, 'p_action': action}, token=token)
