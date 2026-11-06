"""CHEMI 21단계: 실제 Supabase 계정 2개를 이용한 읽기 전용 RLS 점검.

실제 이메일/비밀번호는 프로그램 실행 중 입력받으며 파일에 저장하거나 출력하지 않습니다.
단 두 번의 로그인을 시도합니다. API 사용료가 발생하는 OpenAI 요청은 하지 않습니다.
"""
import getpass
import sys
from urllib.parse import urlencode

import cloud_store
import live_match
import server  # .env만 읽습니다. 웹서버를 시작하지 않습니다.


def safe_query(table, uid, token):
    query = urlencode({'user_id': 'eq.' + uid, 'select': 'user_id', 'limit': '1'})
    rows = cloud_store.request('GET', '/rest/v1/' + table + '?' + query, token=token)
    if not isinstance(rows, list):
        raise RuntimeError('DB가 JSON 리스트를 돌려주지 않았습니다.')
    return rows


def sign_in(label):
    print(f'\n[{label}] 테스트 전용 계정 (아래 입력값은 저장·출력되지 않습니다)')
    email = input('이메일: ').strip()
    password = getpass.getpass('비밀번호(표시 안 됨): ')
    try:
        session = cloud_store.signin(email, password)
    finally:
        del password
    token = session['access_token']
    uid = cloud_store.verify_user(token)['id']
    print(f'{label} 로그인 성공')
    return {'id': uid, 'token': token}


def main():
    if not cloud_store.configured():
        print('Supabase 설정이 없습니다. .env에 URL과 Publishable Key를 설정해 주세요.')
        return 2
    print('CHEMI — 실제 Supabase RLS 읽기 전용 검사')
    print('이미 가입된 서로 다른 테스트 계정 2개를 사용하세요. 회원가입·데이터 수정은 하지 않습니다.')
    print('비밀번호/토큰/닉네임/경험 원문은 출력하지 않습니다.')
    try:
        a = sign_in('A')
        b = sign_in('B')
        if a['id'] == b['id']:
            print('실패: 두 계정이 동일합니다. 서로 다른 계정으로 검사해 주세요.')
            return 2
        failed = []
        for label, viewer, other in (('A→B', a, b), ('B→A', b, a)):
            for table in ('chemi_profiles', 'chemi_analyses'):
                rows = safe_query(table, other['id'], viewer['token'])
                ok = len(rows) == 0
                print(f"{'통과' if ok else '실패'}: {label} 비공개 {table} 조회 차단")
                if not ok:
                    failed.append(label + ' ' + table)
        pa = live_match.my_participation(a['id'], a['token'])
        pb = live_match.my_participation(b['id'], b['token'])
        # Both opted in: public matching profiles should be readable across accounts.
        # Either opted out: querying candidate profiles must return empty/no other account.
        # Request rows must be limited to the current account's sent/received requests.
        for label, account in (('A', a), ('B', b)):
            request_rows = live_match.requests(account['id'], account['token'])
            ok = all(account['id'] in (r['sender_id'], r['recipient_id']) for r in request_rows)
            print(f"{'통과' if ok else '실패'}: {label} 본인 관련 매칭 요청만 조회")
            if not ok:
                failed.append(label + ' request RLS')
        for label, viewer, other, own_opt, other_opt in (
            ('A→B', a, b, pa.get('enabled'), pb.get('enabled')),
            ('B→A', b, a, pb.get('enabled'), pa.get('enabled')),
        ):
            visible_ids = {row['id'] for row in live_match.candidates(viewer['id'], viewer['token'])}
            seen = other['id'] in visible_ids
            expected = bool(own_opt and other_opt)
            if seen == expected:
                print(f'통과: {label} 매칭 참여 동의에 따른 공개 프로필 접근')
            else:
                print(f'실패: {label} 매칭 참여 동의에 따른 공개 프로필 접근')
                failed.append(label + ' matching opt-in')
        if failed:
            print('\n안전 점검 실패: 다른 회원에게 실제 서비스를 공개하지 말고 RLS 정책을 점검하세요.')
            return 1
        print('\n검사 완료: 두 계정 사이 개인 프로필/AI 분석 RLS 및 공개 동의 조건이 통과했습니다.')
        print('주의: 제3자 요청 조회, 수정권한, 실제 요청·수락까지 모두 검증한 것은 아닙니다.')
        return 0
    except (cloud_store.CloudError, OSError, ValueError) as exc:
        # cloud_store errors are generalized upstream; no raw token/password is ever printed.
        print('검사 중단:', str(exc))
        return 2
    except (EOFError, KeyboardInterrupt):
        print('\n취소되었습니다.')
        return 2


if __name__ == '__main__':
    sys.exit(main())
