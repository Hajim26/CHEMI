"""CHEMI cloud account and per-user data access via Supabase Auth + PostgREST.

Uses only a publishable/legacy anon key and the signed-in user's JWT.
NO service_role key, no auth bypass; Postgres RLS remains the final authorization boundary.
"""
import json
import os
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class CloudError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def configured():
    url = os.environ.get('SUPABASE_URL', '').strip()
    key = os.environ.get('SUPABASE_PUBLISHABLE_KEY', '').strip()
    return url.startswith('https://') and bool(key) and 'YOUR_' not in url and 'YOUR_' not in key


def request(method, path, data=None, token=None, *, prefer=None):
    if not configured():
        raise CloudError('Supabase 연결 설정이 없습니다. .env의 SUPABASE_URL과 SUPABASE_PUBLISHABLE_KEY를 확인해 주세요.', 503)
    base = os.environ['SUPABASE_URL'].rstrip('/')
    key = os.environ['SUPABASE_PUBLISHABLE_KEY'].strip()
    body = None if data is None else json.dumps(data, ensure_ascii=False).encode('utf-8')
    headers = {'apikey': key, 'Accept': 'application/json', 'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    else:
        headers['Authorization'] = 'Bearer ' + key if not key.startswith('sb_publishable_') else ''
        if not headers['Authorization']:
            del headers['Authorization']
    if prefer:
        headers['Prefer'] = prefer
    req = Request(base + path, data=body, method=method, headers=headers)
    try:
        with urlopen(req, timeout=18) as response:
            payload = response.read()
            return json.loads(payload.decode('utf-8')) if payload else None
    except HTTPError as exc:
        # Do not include access tokens or raw upstream error bodies in responses/logs.
        code = exc.code
        if code in (400, 401, 403, 422):
            detail = {}
            try:
                detail = json.loads(exc.read().decode('utf-8', errors='replace'))
                raw_code = str(detail.get('error_code') or detail.get('code') or '')
            except Exception:
                raw_code = ''
            if path.startswith('/rest/v1/rpc/chemi_'):
                # Only forward a small, explicitly allowlisted set of SQL function errors.
                safe_errors = (
                    '로그인이 필요합니다.', '기본 프로필을 먼저 저장하세요.',
                    'AI 핵심역량 분석을 먼저 완료하세요.', '자신에게 매칭 요청을 보낼 수 없습니다.',
                    '팀원 매칭 참여에 동의해야 요청할 수 있습니다.',
                    '상대방이 현재 매칭에 참여하지 않습니다.',
                    '요청 정보를 확인하세요.',
                    '매칭 요청은 24시간에 5개까지 보낼 수 있습니다.',
                    '해당 팀원에게 이미 이 공모전의 요청을 보냈습니다.',
                    '해당 요청이 존재하지 않습니다.', '이미 처리된 요청입니다.',
                    '이 요청을 처리할 권한이 없습니다.',
                )
                message = str(detail.get('message', ''))
                raise CloudError(message if message in safe_errors else '매칭 기능을 처리하지 못했어요. SQL 마이그레이션·권한을 확인해 주세요.', 400 if code in (400, 422) else 403) from None
            if path.startswith('/auth/v1/'):
                messages = {
                    'invalid_credentials': '이메일 또는 비밀번호가 올바르지 않습니다.',
                    'email_not_confirmed': '이메일 인증 후 로그인해 주세요.',
                    'weak_password': '비밀번호가 너무 약해요. 더 안전한 비밀번호를 사용해 주세요.',
                    'user_already_exists': '이미 등록된 이메일이에요. 로그인해 주세요.',
                    'over_email_send_rate_limit': '인증 이메일 전송 한도에 도달했어요. 잠시 후 다시 시도해 주세요.',
                    'validation_failed': '입력한 이메일 또는 비밀번호를 확인해 주세요.',
                }
                raise CloudError(messages.get(raw_code, '로그인/회원가입 요청을 처리하지 못했어요. 입력값이나 Supabase 인증 설정을 확인해 주세요.'), 401 if code == 401 else 400) from None
            raise CloudError('데이터베이스 접근이 거부되었어요. SQL 테이블·권한·RLS 정책을 확인해 주세요.', 403) from None
        if code == 404:
            raise CloudError('Supabase 테이블을 찾을 수 없어요. database_setup.sql 실행 여부를 확인해 주세요.', 503) from None
        if code == 409:
            raise CloudError('데이터 저장 충돌이 발생했어요. 다시 시도해 주세요.', 409) from None
        if code == 429:
            raise CloudError('요청이 많아요. 잠시 후 다시 시도해 주세요.', 429) from None
        raise CloudError(f'Supabase 연결 오류 (HTTP {code}). 설정과 네트워크를 확인해 주세요.', 503) from None
    except (URLError, TimeoutError, OSError):
        raise CloudError('Supabase 서버에 연결할 수 없어요. 인터넷과 프로젝트 주소를 확인해 주세요.', 503) from None
    except (ValueError, UnicodeDecodeError):
        raise CloudError('Supabase 서버의 응답을 읽을 수 없어요.', 502) from None


def verify_user(access_token):
    if not access_token:
        raise CloudError('로그인 후 이용할 수 있어요.', 401)
    user = request('GET', '/auth/v1/user', token=access_token)
    if not isinstance(user, dict) or not re.fullmatch(r'[0-9a-fA-F-]{36}', str(user.get('id', ''))):
        raise CloudError('로그인 정보를 확인하지 못했어요.', 401)
    return {'id': user['id'], 'email': user.get('email', '')}


def signup(email, password):
    response = request('POST', '/auth/v1/signup', {'email': email, 'password': password})
    return response or {}


def signin(email, password):
    response = request('POST', '/auth/v1/token?grant_type=password', {'email': email, 'password': password})
    if not isinstance(response, dict) or not response.get('access_token'):
        raise CloudError('로그인에 실패했어요.', 401)
    return response


def refresh(refresh_token):
    response = request('POST', '/auth/v1/token?grant_type=refresh_token', {'refresh_token': refresh_token})
    if not isinstance(response, dict) or not response.get('access_token'):
        raise CloudError('세션을 갱신하지 못했어요. 다시 로그인해 주세요.', 401)
    return response


def signout(access_token):
    try:
        request('POST', '/auth/v1/logout', {}, token=access_token)
    except CloudError:
        pass  # Local browser cookies are still cleared; remote revocation is best-effort.


def fetch_profile(uid, token):
    query = urlencode({'user_id': 'eq.' + uid, 'select': 'user_id,nickname,university,major,grade,consent_at,updated_at', 'limit': '1'})
    rows = request('GET', '/rest/v1/chemi_profiles?' + query, token=token)
    return rows[0] if isinstance(rows, list) and rows else None


def save_profile(uid, token, fields):
    allowed = ('nickname', 'university', 'major', 'grade')
    limits = {'nickname': 24, 'university': 60, 'major': 70, 'grade': 20}
    row = {}
    for name in allowed:
        value = fields.get(name)
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limits[name]:
            raise CloudError(f'{name}: 필수 항목을 확인해 주세요.', 400)
        row[name] = value.strip()
    if row['grade'] not in ('1학년','2학년','3학년','4학년','5학년 이상','휴학생','졸업생'):
        raise CloudError('학년을 정확히 선택해 주세요.', 400)
    if fields.get('consent') is not True:
        raise CloudError('프로필과 핵심역량의 저장·활용에 동의해야 사용할 수 있어요.', 400)
    row.update({'user_id': uid, 'consent_at': datetime.now(timezone.utc).isoformat()})
    rows = request('POST', '/rest/v1/chemi_profiles?on_conflict=user_id', [row], token=token,
                   prefer='resolution=merge-duplicates,return=representation')
    return rows[0] if isinstance(rows, list) and rows else row


def fetch_analysis(uid, token):
    query = urlencode({'user_id': 'eq.' + uid, 'select': 'summary,competencies,caution,updated_at', 'limit': '1'})
    rows = request('GET', '/rest/v1/chemi_analyses?' + query, token=token)
    return rows[0] if isinstance(rows, list) and rows else None


def save_analysis(uid, token, interview, result):
    if not fetch_profile(uid, token):
        raise CloudError('기본 정보를 먼저 저장하고 동의해 주세요.', 409)
    row = {'user_id': uid, 'interview': interview,
           'summary': result['summary'], 'competencies': result['competencies'],
           'caution': result['caution']}
    request('POST', '/rest/v1/chemi_analyses?on_conflict=user_id', [row], token=token,
            prefer='resolution=merge-duplicates,return=minimal')
    return True


def delete_data(uid, token):
    for table in ('chemi_analyses', 'chemi_profiles'):
        request('DELETE', f'/rest/v1/{table}?user_id=eq.{uid}', token=token)
