# CHEMI 21단계 빠른 실행

1. 원래 사용하던 케미 `.env` 파일을 이 폴더에 복사하세요. **새 API 키 발급 불필요.** `.env.example`은 비밀값이 없는 작성 예시입니다.
2. `RUN_STEP21_TESTS_WINDOWS.bat` 실행 — OpenAI/Supabase 호출 없이 로컬 자동 테스트.
3. `RUN_CHEMI_WINDOWS.bat` 실행 → 브라우저 `http://127.0.0.1:8000/`.
4. 실제 계정 A/B로 매칭 참여, 요청·수락을 검증. **동일 계정으로 로그인하면 실제 회원 간 테스트가 불가능합니다.**
5. `RUN_STEP21_LIVE_RLS_WINDOWS.bat`을 실행해 읽기 전용 RLS 점검. 연속 재실행 시 Supabase 로그인 요청 제한이 발생할 수 있으니 반복하지 마세요.
6. `STEP21_RLS_READONLY.sql`을 SQL Editor에서 실행하여 RLS와 권한 확인.
7. `STEP21_TEST_REPORT.md`의 공개 배포 체크리스트가 완료되기 전에는 외부 공개를 권장하지 않습니다.

**개선사항:** 클라우드 연결 시 공모전 새로고침 로그인 필요. OpenAI 비용 보호를 위한 기본 계정별 시간당 30회 제한. 단일 서버 프로세스 기준이며 운영용 공유 API 제한 대체 불가. `.env`에 `CHEMI_AI_REQUESTS_PER_HOUR=30`으로 변경 가능.

**현재 구현 제외:** 17~18단계 팀 구성 확정·채팅. 추천 점수는 예비 평가로만 표시.

## 21단계 로컬 테스트 보정 (2026-11-06)

실제 `.env`에 Supabase가 연결되어 있으면 이전 버전의 오프라인 테스트가 인증 검사에서
`403` 또는 `401`로 실패하는 문제를 수정했습니다. `test_server.py`, `test_matchmaking.py`,
`test_contests.py`의 기존 모의 테스트는 테스트 내부에서만 클라우드를 비활성화하고
독립적으로 실행됩니다. 서비스 코드 `server.py`의 인증·보안 기능은 변경하지 않았습니다.

`RUN_STEP21_TESTS_WINDOWS.bat`을 실행하세요. 실제 사용자 계정 간 데이터 분리,
RLS 정책의 실시간 작동과 실제 매칭 요청·수락은 별도 라이브 테스트가 필요합니다.
