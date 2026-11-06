"""케미 프로젝트 시연용 가상 팀원 100명 DB.

모든 이름/정보는 합성된 가상 자료. 이메일은 example.com 예약 도메인을 사용합니다.
실제 회원가입/동의/연락 기능은 포함하지 않습니다.
"""
from __future__ import annotations
import json
import sqlite3
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / 'data' / 'teammates.db'

# 첫 10명은 기존과 동일하게 유지합니다. 추가 90명은 data/teammates_extra_90.json에서 읽습니다.
FAKE_MEMBERS = [
    dict(id='TM001', nickname='김하린', university='강원대학교', major='디자인학과', grade='3학년', campus='삼척', email='tm001@example.com', bio='사용자 흐름을 설계하고 화면을 구체화하는 일을 좋아해요.',
         skills=[('UI/UX 디자인','디자인'),('Figma 프로토타이핑','디자인'),('사용자 리서치','기획·아이디어')], interests=['AI·개발','기획·아이디어','디자인']),
    dict(id='TM002', nickname='박도윤', university='강원대학교', major='AI소프트웨어학과', grade='2학년', campus='삼척', email='tm002@example.com', bio='작동하는 기능을 빠르게 만드는 백엔드 개발을 선호해요.',
         skills=[('Python 백엔드 개발','AI·개발'),('API 연동','AI·개발'),('SQLite 데이터베이스','AI·개발')], interests=['AI·개발','기획·아이디어']),
    dict(id='TM003', nickname='이하늘', university='강원대학교', major='경영학과', grade='3학년', campus='춘천', email='tm003@example.com', bio='아이디어를 설득력 있는 발표로 전달하는 일을 즐겨요.',
         skills=[('서비스 기획','기획·아이디어'),('발표 및 피칭','기획·아이디어'),('시장 조사','기획·아이디어')], interests=['AI·개발','기획·아이디어']),
    dict(id='TM004', nickname='최서연', university='강원대학교', major='시각디자인학과', grade='4학년', campus='삼척', email='tm004@example.com', bio='기획 내용을 시각 자료로 표현하는 데 강점이 있어요.',
         skills=[('그래픽 디자인','디자인'),('포스터 제작','디자인'),('브랜딩','디자인')], interests=['디자인','지역·사회']),
    dict(id='TM005', nickname='정민재', university='강원대학교', major='전기전자공학과', grade='3학년', campus='삼척', email='tm005@example.com', bio='센서와 장치를 다루는 시제품 제작에 관심이 있어요.',
         skills=[('아두이노 IoT 개발','AI·개발'),('전자회로 설계','AI·개발'),('하드웨어 프로토타입','AI·개발')], interests=['AI·개발','지역·사회']),
    dict(id='TM006', nickname='윤지후', university='강원대학교', major='데이터사이언스학과', grade='2학년', campus='춘천', email='tm006@example.com', bio='수집한 정보를 정리하고 인사이트를 찾는 것을 좋아해요.',
         skills=[('데이터 분석','AI·개발'),('SQL 데이터베이스','AI·개발'),('데이터 시각화','디자인')], interests=['AI·개발','지역·사회']),
    dict(id='TM007', nickname='한지민', university='강원대학교', major='사회복지학과', grade='3학년', campus='춘천', email='tm007@example.com', bio='현장에서 사용자 의견을 듣고 문제를 정의하고 싶어요.',
         skills=[('현장 조사','지역·사회'),('인터뷰 진행','지역·사회'),('사회문제 조사','지역·사회')], interests=['지역·사회','기획·아이디어']),
    dict(id='TM008', nickname='송현우', university='강원대학교', major='컴퓨터공학과', grade='4학년', campus='춘천', email='tm008@example.com', bio='사용자가 실제로 만지는 웹 인터페이스를 구현해요.',
         skills=[('프론트엔드 개발','AI·개발'),('React 웹앱 제작','AI·개발'),('웹 접근성','디자인')], interests=['AI·개발','디자인']),
    dict(id='TM009', nickname='오수빈', university='강원대학교', major='행정학과', grade='2학년', campus='삼척', email='tm009@example.com', bio='정책과 공공문제에 필요한 근거 자료를 찾는 일을 해요.',
         skills=[('정책 자료 조사','지역·사회'),('공공서비스 기획','기획·아이디어'),('보고서 작성','기획·아이디어')], interests=['지역·사회','기획·아이디어']),
    dict(id='TM010', nickname='강예린', university='강원대학교', major='미디어커뮤니케이션학과', grade='3학년', campus='춘천', email='tm010@example.com', bio='프로젝트를 알기 쉬운 이야기와 영상으로 만드는 것을 좋아해요.',
         skills=[('영상 편집','디자인'),('SNS 콘텐츠 홍보','디자인'),('대외 발표','기획·아이디어')], interests=['디자인','기획·아이디어','지역·사회']),
]


ADDITIONAL_DATA = ROOT / 'data' / 'teammates_extra_90.json'
EXPECTED_TOTAL = 100

def load_extra_profiles(path=ADDITIONAL_DATA):
    """추가 90명의 합성 인물만 로드합니다. 실제 회원 DB와 섞지 않습니다."""
    raw=json.loads(Path(path).read_text(encoding='utf-8'))
    if len(raw)!=90 or len({m['id'] for m in raw})!=90:
        raise ValueError('추가 가상인물 데이터는 중복 없이 정확히 90명이어야 합니다.')
    if any(not m.get('is_synthetic') or not str(m.get('email','')).endswith('@example.com') for m in raw):
        raise ValueError('추가 프로필에는 합성 데이터만 들어갈 수 있습니다.')
    result=[]
    for m in raw:
        item=dict(m)
        item['skills']=[(x['name'],x['category']) for x in m['skills']]
        result.append(item)
    return result

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS team_members (
  id TEXT PRIMARY KEY, nickname TEXT NOT NULL, university TEXT NOT NULL,
  major TEXT NOT NULL, grade TEXT NOT NULL, campus TEXT NOT NULL,
  email TEXT NOT NULL, bio TEXT NOT NULL, is_synthetic INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS member_skills (
  id INTEGER PRIMARY KEY AUTOINCREMENT, member_id TEXT NOT NULL,
  name TEXT NOT NULL, category TEXT NOT NULL,
  FOREIGN KEY(member_id) REFERENCES team_members(id) ON DELETE CASCADE,
  UNIQUE(member_id,name)
);
CREATE TABLE IF NOT EXISTS member_interests (
  id INTEGER PRIMARY KEY AUTOINCREMENT, member_id TEXT NOT NULL,
  category TEXT NOT NULL,
  FOREIGN KEY(member_id) REFERENCES team_members(id) ON DELETE CASCADE,
  UNIQUE(member_id,category)
);
"""

def seed_database(path=DATABASE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as con, con:
        con.executescript(SCHEMA)
        con.execute('BEGIN') if not con.in_transaction else None
        for m in FAKE_MEMBERS + load_extra_profiles():
            con.execute('INSERT OR IGNORE INTO team_members (id,nickname,university,major,grade,campus,email,bio,is_synthetic) VALUES (?,?,?,?,?,?,?,?,1)',
                        (m['id'],m['nickname'],m['university'],m['major'],m['grade'],m['campus'],m['email'],m['bio']))
            for name, category in m['skills']:
                con.execute('INSERT OR IGNORE INTO member_skills (member_id,name,category) VALUES (?,?,?)',(m['id'],name,category))
            for category in m['interests']:
                con.execute('INSERT OR IGNORE INTO member_interests (member_id,category) VALUES (?,?)',(m['id'],category))
    return path

def get_members(path=DATABASE, include_email=False):
    path=Path(path)
    if not path.exists():
        seed_database(path)
    else:
        # 기존 10명 DB를 가진 사용자가 파일을 교체하지 않아도 90명을 추가합니다.
        with closing(sqlite3.connect(path)) as check:
            n=check.execute('SELECT COUNT(*) FROM team_members').fetchone()[0]
        if n<EXPECTED_TOTAL:
            seed_database(path)
    with closing(sqlite3.connect(path)) as con:
        con.row_factory=sqlite3.Row
        members=[dict(row) for row in con.execute('SELECT * FROM team_members ORDER BY id')]
        skills=list(con.execute('SELECT member_id,name,category FROM member_skills ORDER BY id'))
        interests=list(con.execute('SELECT member_id,category FROM member_interests ORDER BY id'))
    by_id={m['id']:m for m in members}
    for member in members:
        member['is_synthetic']=bool(member['is_synthetic'])
        member['skills']=[]
        member['interests']=[]
        if not include_email: member.pop('email',None)
    for record in skills:
        by_id[record['member_id']]['skills'].append({'name':record['name'],'category':record['category']})
    for record in interests:
        by_id[record['member_id']]['interests'].append(record['category'])
    return members

if __name__=='__main__':
    seed_database()
    print(f'가상 학생 {len(get_members())}명의 SQLite 데이터베이스 생성: {DATABASE}')
    (ROOT/'data'/'teammates_demo.json').write_text(json.dumps(get_members(include_email=True),ensure_ascii=False,indent=2),encoding='utf-8')
