"""강원대학교 공개 공모안내 목록 수집.

- 수집 전 robots.txt 확인 (확인 불가/차단 시 수집 안 함)
- 공개 목록 1~2쪽만 제한적으로 요청; 상세·첨부파일 수집 안 함
- 게시글 원문 링크·게시일만 표시 (마감/모집중 여부 추정 안 함)
- 직전 정상 수집 결과 JSON·CSV 캐싱
"""
from __future__ import annotations

import csv
import io
import json
import re
import threading
import time
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

BASE = 'https://www.kangwon.ac.kr'
BOARD = BASE + '/ko/bbs/719/list.do'
ROBOTS = BASE + '/robots.txt'
AGENT = 'CHEMI-StudentContestViewer/1.0 (respectful single-board reader)'
ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
CACHE = DATA / 'contests.json'
CSV = DATA / 'contests.csv'
PAGES = 2
INTER_PAGE_DELAY = 2.0
MIN_REFRESH_SECONDS = 60.0
MAX_RESPONSE = 1_500_000
KST = timezone(timedelta(hours=9))
LOCK = threading.Lock()
LAST_ATTEMPT = 0.0

class CrawlError(Exception):
    pass


def fetch(url):
    """Only official hostname; no follow to non-official websites, cap size/time."""
    if urlsplit(url).netloc != 'www.kangwon.ac.kr' or urlsplit(url).scheme != 'https':
        raise CrawlError('허용되지 않은 외부 주소입니다.')
    request = Request(url, headers={
        'User-Agent': AGENT,
        'Accept': 'text/html,text/plain;q=0.8,*/*;q=0.5',
        'Accept-Language': 'ko-KR,ko;q=0.9',
    })
    with urlopen(request, timeout=12) as resp:
        dest = resp.geturl()
        if urlsplit(dest).hostname != 'www.kangwon.ac.kr' or urlsplit(dest).scheme != 'https':
            raise CrawlError('외부 사이트로 이동하여 수집을 중단했습니다.')
        content = resp.read(MAX_RESPONSE + 1)
        if len(content) > MAX_RESPONSE:
            raise CrawlError('페이지 용량이 너무 커서 수집을 중단했습니다.')
        charset = resp.headers.get_content_charset() or 'utf-8'
        return content.decode(charset, errors='replace')


def can_crawl():
    try:
        rules = fetch(ROBOTS)
    except HTTPError as e:
        if e.code in (404, 410):
            return True  # robots.txt absent: no published disallow rules
        if e.code in (401, 403):
            raise CrawlError('강원대학교 사이트가 자동 접근을 제한했습니다.') from None
        raise CrawlError(f'robots.txt 확인 오류(HTTP {e.code}). 사이트 접근을 보류합니다.') from None
    except (URLError, TimeoutError, OSError, UnicodeError):
        raise CrawlError('robots.txt에 연결할 수 없어 자동 수집을 보류했어요. 네트워크 상태를 확인해 주세요.') from None
    parser = RobotFileParser()
    parser.parse(rules.splitlines())
    if not parser.can_fetch(AGENT, BOARD):
        raise CrawlError('강원대학교 robots.txt에서 해당 게시판 자동 수집을 허용하지 않습니다.')
    # Only page 1+2; per-page check after building URL.
    return parser


def clean(text):
    return re.sub(r'\s+', ' ', text).strip()


def classify(title):
    s = title.lower()
    if re.search(r'인공지능|\bai\b|소프트웨어|해커톤|코딩|데이터|개발|정보통신|디지털|스마트', s):
        return 'AI·개발'
    if re.search(r'디자인|포스터|미디어|영상|콘텐츠|웹툰|일러스트', s):
        return '디자인'
    if re.search(r'지역|사회|환경|기후|탄소|봉사|안전|공공', s):
        return '지역·사회'
    if re.search(r'기획|아이디어|창업|혁신|발명|경진대회|공모전', s):
        return '기획·아이디어'
    return '기타'


def url_from_attrs(attrs):
    a = dict(attrs)
    for key in ('href', 'onclick', 'data-href', 'data-url'):
        raw = a.get(key, '')
        if not raw:
            continue
        # Prefer explicit published URL parameters; ignore javascript: itself.
        m = re.search(r'[?&]pstSn=(\d+)', raw)
        if m:
            return BASE + f'/ko/bbs/719/detail.do?pstSn={m.group(1)}'
        # Fallback for function call with post ID argument, only if it looks like detail/view route.
        if re.search(r'detail\.do|fnView|goView|viewPost|fnDetail|fnSelect', raw, re.I):
            m = re.search(r'\b(\d{4,})\b', raw)
            if m:
                return BASE + f'/ko/bbs/719/detail.do?pstSn={m.group(1)}'
    return ''


class ListingParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_row = False
        self.in_cell = False
        self.cells = []
        self.cell_chunks = []
        self.anchors = []
        self.anchor = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.in_row = True
            self.cells = []
            self.anchors = []
            self.in_cell = False
        elif self.in_row and tag in ('td', 'th'):
            self.in_cell = True
            self.cell_chunks = []
        elif self.in_row and tag == 'a':
            self.anchor = {'url': url_from_attrs(attrs), 'text': []}

    def handle_data(self, data):
        if self.in_row and self.in_cell:
            self.cell_chunks.append(data)
        if self.anchor is not None:
            self.anchor['text'].append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.anchor is not None:
            self.anchor['text'] = clean(''.join(self.anchor['text']))
            self.anchors.append(self.anchor)
            self.anchor = None
        if tag in ('td', 'th') and self.in_row and self.in_cell:
            self.cells.append(clean(''.join(self.cell_chunks)))
            self.in_cell = False
        if tag == 'tr' and self.in_row:
            self.rows.append((self.cells, self.anchors))
            self.in_row = False


def parse_list(html):
    parser = ListingParser()
    parser.feed(html)
    items = []
    seen = set()
    for cells, anchors in parser.rows:
        # Expected: [번호, 캠퍼스, 제목, 등록일시, 조회수]
        if len(cells) < 4:
            continue
        anchor = next((a for a in anchors if a['url']), None)
        if not anchor:
            continue
        title = anchor['text'] or (cells[2] if len(cells) >= 3 else '')
        title = clean(title)
        if not title or len(title) > 300:
            continue
        postdate = next((m.group(0).replace('.', '-') for cell in cells for m in [re.search(r'20\d{2}[.\-]\d{1,2}[.\-]\d{1,2}', cell)] if m), '')
        if not postdate:
            continue
        url = anchor['url']
        if url in seen:
            continue
        seen.add(url)
        campus = cells[1][:35] if len(cells) > 1 else ''
        items.append({
            'id': urlsplit(url).query.removeprefix('pstSn='),
            'title': title,
            'campus': campus,
            'date': postdate,
            'url': url,
            'category': classify(title),
            'description': f'강원대학교 공모안내 등록일 {postdate} · 캠퍼스 {campus or "미표기"}',
            'roles': [],
            'detail': '지원 자격과 접수 기한은 원문에서 확인해 주세요.',
            'is_sample': False,
        })
    return items


def read_cache():
    try:
        obj = json.loads(CACHE.read_text(encoding='utf-8'))
        if isinstance(obj, dict) and isinstance(obj.get('items'), list):
            return obj
    except (OSError, json.JSONDecodeError, UnicodeError):
        pass
    return {'items': [], 'updated_at': None, 'source': BOARD}


def save_cache(items):
    DATA.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(KST).isoformat(timespec='seconds')
    obj = {'items': items, 'updated_at': stamp, 'source': BOARD}
    tmp = CACHE.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(CACHE)
    tmpcsv = CSV.with_suffix('.csv.tmp')
    with tmpcsv.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['id','title','campus','date','category','url'])
        w.writeheader()
        for c in items:
            w.writerow({field:c.get(field, '') for field in w.fieldnames})
    tmpcsv.replace(CSV)
    return obj


def refresh():
    global LAST_ATTEMPT
    if not LOCK.acquire(blocking=False):
        raise CrawlError('이미 공모전 목록을 새로고침하고 있어요.')
    try:
        moment = time.monotonic()
        if moment - LAST_ATTEMPT < MIN_REFRESH_SECONDS:
            remain = int(MIN_REFRESH_SECONDS - (moment - LAST_ATTEMPT)) + 1
            raise CrawlError(f'학교 서버 보호를 위해 {remain}초 후 다시 새로고침할 수 있어요.')
        LAST_ATTEMPT = moment
        policy = can_crawl()
        results = []
        seen = set()
        for i in range(1, PAGES + 1):
            url = BOARD if i == 1 else (BOARD + f'?pageIndex={i}&pageItm=10&searchGbn=0&searchOrderSort=0')
            if policy is not True and not policy.can_fetch(AGENT, url):
                raise CrawlError('수집 대상 페이지가 robots.txt에서 차단되어 있어요.')
            if i > 1:
                time.sleep(INTER_PAGE_DELAY)
            try:
                html = fetch(url)
            except HTTPError as exc:
                raise CrawlError(f'학교 게시판 접속 실패(HTTP {exc.code}).') from None
            except (URLError, TimeoutError, OSError):
                raise CrawlError('학교 게시판 연결에 실패했어요. 인터넷 연결을 확인해 주세요.') from None
            for item in parse_list(html):
                if item['url'] not in seen:
                    results.append(item)
                    seen.add(item['url'])
        if not results:
            raise CrawlError('공고 목록을 읽지 못했어요. 사이트 구조가 바뀌었을 수 있습니다. 기존 목록은 유지해요.')
        obj = save_cache(results)
        return obj
    finally:
        LOCK.release()
