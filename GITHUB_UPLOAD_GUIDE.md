# CHEMI GitHub 저장소 연결 및 업로드 안내

이 패키지는 기존 최신 프로젝트 56개 파일을 **삭제하지 않고 모두 보존**하고, GitHub용 안내서와 CI를 추가한 버전입니다.

## 1) GitHub 저장소 생성

1. GitHub 로그인 → 우측 상단 `+` → **New repository**.
2. Repository name: `CHEMI` (예시). 처음에는 **Private** 권장.
3. 기존 파일을 직접 올릴 예정이므로 **Add a README file**, `.gitignore`, License 자동 생성은 처음에는 선택하지 마세요. 이 프로젝트에 이미 있습니다.
4. **Create repository** 클릭.

## 2) Windows에서 업로드 (Git 설치 필요)

이 ZIP의 `CHEMI` 폴더에서 탐색기 주소창에 `cmd`를 입력하거나 터미널을 엽니다.
다음 명령어에서 `<GitHub_ID>`는 본인의 ID로 교체하세요.

```powershell
git init
git branch -M main
git add .
git status
git commit -m "Initial CHEMI MVP"
git remote add origin https://github.com/<GitHub_ID>/CHEMI.git
git push -u origin main
```

이미 Git 저장소가 초기화돼 있다면 `git init`과 `git remote add origin`을 반복하지 말고 `git remote -v`로 주소를 확인하세요.
GitHub가 인증을 요구하면 브라우저 인증/자격 증명 관리자를 사용하고, **비밀번호·토큰을 코드나 채팅에 붙여 넣지 마세요.**

## 3) 업로드 확인

GitHub 저장소에 다음 파일이 보이는지 확인합니다.

- `index.html`, `server.py`, `matchmaking.py`, `contests.py`, `team_database.py`
- `.gitignore`, `.env.example`, `requirements.txt`
- `data/teammates.db`, `data/teammates_100.csv`, `data/teammates_extra_90.json` (모두 가상 데이터)
- `test_*.py`, `test_*.js`, `.github/workflows/tests.yml`

**`.env`가 보이면 안 됩니다.** 만약 비밀키를 이미 업로드했다면 파일을 삭제하는 것만으로 부족하므로 해당 키를 교체하고 저장소 기록도 안전하게 처리해야 합니다.

## 4) GitHub에 올린 뒤 수정하기

```powershell
git add .
git commit -m "Update CHEMI MVP"
git push
```

## 5) 웹앱 배포는 별도 단계

GitHub는 코드 저장소이며 이 프로젝트의 Python 백엔드를 자동 실행하지 않습니다. `index.html`을 GitHub Pages에 올리는 것만으로는 AI/Supabase 프록시 API가 동작하지 않습니다. 별도의 Python 서버 호스팅과 환경변수 설정이 필요합니다.

## 주의

- `SUPABASE_PUBLISHABLE_KEY`는 공개 클라이언트용 키지만, RLS 정책 보호가 필수입니다.
- `OPENAI_API_KEY`와 Supabase Secret/Service Role 키는 GitHub에 업로드하지 마세요.
- 테스트용 합성 팀원 데이터만 포함합니다. 실제 사용자 데이터가 담긴 DB 백업이나 수집 결과물은 업로드하지 마세요.
- 공개 저장소 전환 전 개인정보/라이선스/공식 공고 사이트 이용조건을 검토하세요.
