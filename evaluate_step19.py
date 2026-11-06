"""재현 가능한 합성 후보 비교. 실제 매칭 정확도 검증이 아닙니다."""
from pathlib import Path
import matchmaking as m


def member(key, skill, domain, interest):
    return {'id': key, 'nickname': key, 'major': '가상 전공',
            'is_synthetic': True, 'skills': [{'name': skill, 'category': domain}],
            'interests': [interest]}

scenarios = [
    ('개발자에게 디자인 보완', 'Python 개발', '서비스 디자인 공모전', '디자인',
     member('중복 개발', 'Python 백엔드 개발','AI·개발','디자인'),
     member('디자인 보완','UI UX 디자인','디자인','디자인')),
    ('개발자에게 데이터 보완', 'Python 백엔드 개발', 'AI 서비스 개발 및 데이터 활용 공모전','AI·개발',
     member('중복 개발','React 웹 개발','AI·개발','AI·개발'),
     member('데이터 보완','SQL 데이터 분석','AI·개발','AI·개발')),
    ('데이터 사용자에게 발표 보완','SQL 데이터 분석','데이터 활용 발표 경진대회','AI·개발',
     member('중복 데이터','SQL 데이터 처리','AI·개발','AI·개발'),
     member('발표 보완','대중 발표 피칭','기획·아이디어','AI·개발')),
    ('지역 조사 사용자에게 기획 보완','지역 현장 조사','지역사회 문제해결 아이디어 공모전','지역·사회',
     member('중복 현장','지역 현장 조사','지역·사회','지역·사회'),
     member('기획 보완','서비스 기획','기획·아이디어','지역·사회')),
    ('기획 사용자에게 디자인 보완','서비스 기획','서비스 디자인 공모전','디자인',
     member('중복 기획','서비스 기획','기획·아이디어','디자인'),
     member('디자인 보완','UI UX 디자인','디자인','디자인')),
    ('개발 사용자에게 IoT 보완','Python 개발','로봇 센서 IoT 개발 경진대회','AI·개발',
     member('중복 개발','Python 백엔드 개발','AI·개발','AI·개발'),
     member('IoT 보완','아두이노 센서 회로','AI·개발','AI·개발')),
]
rows=[]
for label,user,title,cat,duplicate,complement in scenarios:
    strengths=[{'name':user}]
    contest={'id':label,'title':title,'category':cat}
    score_a=m.score_candidate(contest,strengths,duplicate)[0]
    score_b=m.score_candidate(contest,strengths,complement)[0]
    rows.append((label,score_a,score_b,score_b>score_a))

path=Path(__file__).with_name('STEP19_매칭_검증.md')
with path.open('w',encoding='utf-8') as out:
    out.write('# CHEMI 19단계 — 매칭 평가 검증 (합성 사례)\n\n')
    out.write('아래 비교는 **설계자가 만든 가상 입력 6건**을 이용한 단위 검증입니다. 실제 사용자 선택, 추천 정확도, 협업 성공률을 증명하지 않습니다.\n\n')
    out.write('| 사례 | 같은/중복 역할 후보 | 보완 역할 후보 | 보완 후보 우위 |\n|---|---:|---:|---|\n')
    for label,a,b,success in rows:
        out.write(f'| {label} | {a} | {b} | {"확인" if success else "미충족"} |\n')
    out.write('\n**합성 사례 결과:** '+str(sum(r[3] for r in rows))+'/'+str(len(rows))+'건에서 기대한 방향으로 정렬. 이 결과는 실사용 평가의 대체 지표가 아닙니다.\n')
    out.write('\n**유의사항:** 실제 공모전 모집 요강을 분석하지 않고 제목·분야를 기준으로 요구 역할을 추정합니다. 후보의 수행 경험 원문과 비공개 정보를 다른 회원이나 AI 후보 검색에 제공하지 않습니다. 경험 근거 20점은 현재 검증 데이터가 없어서 0점으로 처리합니다.\n')
print('SCENARIOS', rows)
print('REPORT',path)
