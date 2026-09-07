# -*- coding: utf-8 -*-
"""제안서 4종 내용 교정 — word/document.xml 문자열 외과수술.

  python tools/docx_text_fix.py          # 교정본 4종 생성 + 검증
  python tools/docx_text_fix.py --verify # 이미 만든 교정본만 재검증

설계 원칙
  · ElementTree 로 재직렬화하지 않는다. 재직렬화는 파일 전체의 namespace 접두사를
    다시 쓰기 때문에, '지정한 문자열만 바뀌었다'는 증명이 불가능해진다.
    따라서 모든 편집은 document.xml 원본 바이트 위의 부분 치환(splice)으로 한다.
  · 모든 연산은 매치 수를 단정(assert)한다. 기대치와 다르면 OpError 로 중단한다.
  · 원본은 절대 덮어쓰지 않는다. 원본을 <이름>_교정.docx 로 복사한 뒤 복사본만 고친다.
  · 나머지 바이트·zip 항목·압축방식은 그대로 보존한다.
"""
import difflib
import io
import os
import re
import shutil
import sys
import zipfile
from xml.etree import ElementTree as ET

DOC = 'word/document.xml'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

# <w:tbl> 은 잡고 <w:tblPr> 은 잡지 않는 여닫이 패턴
RE_TBL_O = re.compile(r'<w:tbl(?:\s[^>]*)?>')
RE_TBL_C = re.compile(r'</w:tbl>')
RE_TR_O = re.compile(r'<w:tr(?:\s[^>]*)?>')
RE_TR_C = re.compile(r'</w:tr>')
RE_TC_O = re.compile(r'<w:tc(?:\s[^>]*)?>')
RE_TC_C = re.compile(r'</w:tc>')
RE_P_O = re.compile(r'<w:p(?:\s[^>]*)?>')
RE_P_C = re.compile(r'</w:p>')
RE_WT = re.compile(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>|<w:t\s*/>', re.S)

LOG = []


class OpError(Exception):
    """연산이 기대한 매치 수를 얻지 못했다."""


def _log(line):
    LOG.append(line)
    print(line)


# ---------------------------------------------------------------- zip 입출력

def _load(path):
    with zipfile.ZipFile(path) as z:
        infos = list(z.infolist())
        blobs = {i.filename: z.read(i.filename) for i in infos}
    return infos, blobs


def _save(path, infos, blobs):
    """원본 항목 순서·압축방식·타임스탬프·속성을 그대로 두고 다시 압축한다."""
    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w') as zo:
        for i in infos:
            zi = zipfile.ZipInfo(i.filename, date_time=i.date_time)
            zi.compress_type = i.compress_type
            zi.external_attr = i.external_attr
            zi.internal_attr = i.internal_attr
            zi.create_system = i.create_system
            zi.flag_bits = i.flag_bits & ~0x08
            zo.writestr(zi, blobs[i.filename])
    os.replace(tmp, path)


def _edit(path, fn):
    """document.xml 을 문자열로 열어 fn 으로 고치고 그대로 되돌려 넣는다."""
    infos, blobs = _load(path)
    xml = blobs[DOC].decode('utf-8')
    out = fn(xml)
    blobs[DOC] = out.encode('utf-8')
    _save(path, infos, blobs)


# ---------------------------------------------------------------- 구조 스캔

def _spans(xml, ro, rc, start=0, end=None):
    """[start, end) 안에서 최상위 여닫이 구간 목록을 깊이 인식으로 뽑는다."""
    end = len(xml) if end is None else end
    marks = []
    for m in ro.finditer(xml, start, end):
        marks.append((m.start(), m.end(), 1))
    for m in rc.finditer(xml, start, end):
        marks.append((m.start(), m.end(), -1))
    marks.sort()
    out, depth, s = [], 0, None
    for a, b, d in marks:
        if d == 1:
            if depth == 0:
                s = a
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                out.append((s, b))
            elif depth < 0:
                raise OpError('여닫이 불균형 at %d' % a)
    if depth:
        raise OpError('여닫이 미종료 (depth=%d)' % depth)
    return out


def _cell_text(frag):
    return ''.join(m.group(1) or '' for m in RE_WT.finditer(frag))


def _xml_unescape(s):
    return (s.replace('&lt;', '<').replace('&gt;', '>')
             .replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&'))


def _xml_escape(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _find_table(xml, table_key):
    """머리글 행(첫 <w:tr>) 안에 table_key 가 있는 표를 1개만 찾는다."""
    hits = []
    for s, e in _spans(xml, RE_TBL_O, RE_TBL_C):
        rows = _spans(xml, RE_TR_O, RE_TR_C, s, e)
        if not rows:
            continue
        hdr = _xml_unescape(_cell_text(xml[rows[0][0]:rows[0][1]]))
        if table_key in hdr:
            hits.append((s, e))
    if len(hits) != 1:
        raise OpError('표 매치 %d건 (기대 1): table_key=%r' % (len(hits), table_key))
    return hits[0]


def _find_row(xml, tbl, row_key):
    """첫 칸 텍스트가 row_key 인 행을 1개만 찾는다."""
    rows = _spans(xml, RE_TR_O, RE_TR_C, tbl[0], tbl[1])
    hits = []
    for rs, re_ in rows:
        cells = _spans(xml, RE_TC_O, RE_TC_C, rs, re_)
        if not cells:
            continue
        first = _xml_unescape(_cell_text(xml[cells[0][0]:cells[0][1]])).strip()
        if first == row_key:
            hits.append((rs, re_, cells))
    if len(hits) != 1:
        raise OpError('행 매치 %d건 (기대 1): row_key=%r' % (len(hits), row_key))
    return hits[0]


def _set_wt(frag, text):
    """조각(칸/문단) 안의 유일한 <w:t> 값을 text 로 바꾼다. 1개가 아니면 예외."""
    ms = list(RE_WT.finditer(frag))
    if len(ms) != 1:
        raise OpError('<w:t> %d개 (기대 1): %r' % (len(ms), frag[:120]))
    m = ms[0]
    sp = ' xml:space="preserve"' if text != text.strip() else ''
    return frag[:m.start()] + '<w:t%s>%s</w:t>' % (sp, _xml_escape(text)) + frag[m.end():]


# ---------------------------------------------------------------- 공개 연산

def replace(docx, pairs):
    """<w:t> 값 안의 정확한 문자열 치환.

    pairs: [(찾기, 바꾸기)] 또는 [(찾기, 바꾸기, 기대매치수)]
    기대 매치 수(기본 1)와 다르면 OpError.
    """
    def go(xml):
        for item in pairs:
            old, new = item[0], item[1]
            want = item[2] if len(item) > 2 else 1
            n = xml.count(old)
            if n != want:
                raise OpError('치환 매치 %d건 (기대 %d): %r' % (n, want, old))
            _assert_single_run(xml, old)
            xml = xml.replace(old, new)
            # 바꿀 문자열이 찾을 문자열을 품는 경우(꼬리 덧붙이기)를 감안한 잔존 검사
            left = xml.count(old)
            if left != want * new.count(old):
                raise OpError('치환 후 잔존 %d건 (기대 %d): %r'
                              % (left, want * new.count(old), old))
            _log('    replace  x%d  %r -> %r' % (n, old, new))
        return xml
    _edit(docx, go)


def _assert_single_run(xml, needle):
    """needle 의 모든 출현이 하나의 <w:t> 안에 온전히 들어있는지 확인한다."""
    i = xml.find(needle)
    while i != -1:
        j = i + len(needle)
        # 직전 <w:t 여는 태그 / 직전 </w:t> 닫는 태그 위치 비교
        opens = [m.end() for m in re.finditer(r'<w:t(?:\s[^>]*)?>', xml[:i])]
        closes = [m.end() for m in re.finditer(r'</w:t>', xml[:i])]
        if not opens or (closes and closes[-1] > opens[-1]):
            raise OpError('%r 가 <w:t> 밖에 있다 (offset %d)' % (needle, i))
        nxt_close = xml.find('</w:t>', j)
        nxt_open = re.search(r'<w:t(?:\s[^>]*)?>', xml[j:])
        if nxt_close == -1 or (nxt_open and j + nxt_open.start() < nxt_close):
            raise OpError('%r 가 여러 run 에 걸쳐 있다 (offset %d)' % (needle, i))
        i = xml.find(needle, j)


def set_cells(docx, table_key, row_key, values):
    """머리글 문자열로 표를, 첫 칸 텍스트로 행을 찾아 지정 칸 텍스트를 세팅한다.

    values: {열번호(0부터): 텍스트}
    """
    def go(xml):
        tbl = _find_table(xml, table_key)
        rs, re_, cells = _find_row(xml, tbl, row_key)
        before = [_xml_unescape(_cell_text(xml[a:b])) for a, b in cells]
        row = xml[rs:re_]
        # 뒤 칸부터 고쳐 앞 칸 오프셋이 흐트러지지 않게 한다
        for ci in sorted(values, reverse=True):
            if ci >= len(cells):
                raise OpError('열 %d 없음 (칸 %d개): %s' % (ci, len(cells), row_key))
            a, b = cells[ci][0] - rs, cells[ci][1] - rs
            row = row[:a] + _set_wt(row[a:b], values[ci]) + row[b:]
        # 길이가 바뀌었으므로 새 행에서 칸 경계를 다시 잡아 결과를 확인한다
        after = [_xml_unescape(_cell_text(row[a:b]))
                 for a, b in _spans(row, RE_TC_O, RE_TC_C)]
        if len(after) != len(before):
            raise OpError('칸 수 변동: %d -> %d' % (len(before), len(after)))
        _log('    set_cells  [%s] %s: %s -> %s'
             % (table_key, row_key, before, after))
        return xml[:rs] + row + xml[re_:]
    _edit(docx, go)


def insert_row_after(docx, table_key, after_row_key, cells):
    """찾은 행의 <w:tr> 마크업을 서식 틀로 복제해 칸 텍스트만 바꿔 뒤에 끼운다."""
    def go(xml):
        tbl = _find_table(xml, table_key)
        rs, re_, tcs = _find_row(xml, tbl, after_row_key)
        if len(cells) != len(tcs):
            raise OpError('칸 수 불일치: 지정 %d, 틀 %d' % (len(cells), len(tcs)))
        row = xml[rs:re_]
        for ci in range(len(tcs) - 1, -1, -1):
            a, b = tcs[ci][0] - rs, tcs[ci][1] - rs
            row = row[:a] + _set_wt(row[a:b], cells[ci]) + row[b:]
        _log('    insert_row_after  [%s] after %s: %s'
             % (table_key, after_row_key, cells))
        return xml[:re_] + row + xml[re_:]
    _edit(docx, go)


def insert_para_after(docx, anchor_text, text):
    """앵커 문단의 <w:p> 마크업(pPr·rPr 포함)을 그대로 복제해 뒤에 문단을 끼운다."""
    def go(xml):
        n = xml.count(anchor_text)
        if n != 1:
            raise OpError('앵커 문단 매치 %d건 (기대 1): %r' % (n, anchor_text[:40]))
        i = xml.index(anchor_text)
        opens = [m.start() for m in RE_P_O.finditer(xml, 0, i)]
        if not opens:
            raise OpError('앵커의 <w:p> 를 못 찾음')
        ps = opens[-1]
        mc = RE_P_C.search(xml, i)
        pe = mc.end()
        para = _set_wt(xml[ps:pe], text)
        _log('    insert_para_after  %r\n                       -> %r'
             % (anchor_text[:34] + '…', text))
        return xml[:pe] + para + xml[pe:]
    _edit(docx, go)


# ---------------------------------------------------------------- 검증 도구

def blocks(docx):
    """본문·표의 모든 <w:t> 를 블록(문단/칸) 단위 텍스트 목록으로 뽑는다."""
    root = ET.fromstring(zipfile.ZipFile(docx).read(DOC))
    out = []
    for p in root.iter(W + 'p'):
        t = ''.join(n.text or '' for n in p.iter(W + 't'))
        if t.strip():
            out.append(t)
    return out


def table_stats(docx):
    root = ET.fromstring(zipfile.ZipFile(docx).read(DOC))
    tbls = list(root.iter(W + 'tbl'))
    return len(tbls), sum(len(t.findall(W + 'tr')) for t in tbls)


def diff_blocks(src, dst):
    a, b = blocks(src), blocks(dst)
    changed = []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        changed.append((tag, a[i1:i2], b[j1:j2]))
    return changed


# ---------------------------------------------------------------- 교정 목록

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
P = lambda *x: os.path.join(ROOT, 'proposals', *x)

SRC = {
    'A': '제안서_A안_교육용AI스킬_아카이브_구축.docx',
    'B': '제안서_B안_교육용AI스킬_포털_구축.docx',
    'C': '제안서_C안_교육용AI스킬_포털구축_및_교원연수.docx',
    'ALL': '제안서_통합비교본_부산교육청_교육용AI스킬.docx',
}

# A · 단순 문자열 치환 (문서 -> [(찾기, 바꾸기)])
TEXT_FIX = {
    'A': [('본 포털은', '본 아카이브는'),
          ('본문 Ⅲ-4', '본문 Ⅲ-3'),
          ('7만 명가', '7만 명이')],
    'B': [('왜 지금, 부산에 스킬 아카이브인가', '왜 지금, 부산에 스킬 포털인가'),
          ('아카이브 시스템 개발과 교육용 콘텐츠 제작', '포털 시스템 개발과 교육용 콘텐츠 제작'),
          ('본문 Ⅲ-4', '본문 Ⅲ-3'),
          ('7만 명가', '7만 명이'),
          ('요구사항 전체(21개 ID)', '요구사항 전체(22개 ID)')],
    'C': [('왜 지금, 부산에 스킬 아카이브인가', '왜 지금, 부산에 스킬 포털인가'),
          ('아카이브 시스템 개발과 교육용 콘텐츠 제작', '포털 시스템 개발과 교육용 콘텐츠 제작'),
          ('첫 단계 실행 인프라', '실행 인프라'),
          ('율리밋', '레이트리밋'),
          ('연수으로', '연수로'),
          ('본문 Ⅲ-4', '본문 Ⅲ-3'),
          ('7만 명가', '7만 명이'),
          ('요구사항 전체(28개 ID)', '요구사항 전체(29개 ID)')],
    'ALL': [('요구사항 28개 ID', '요구사항 29개 ID'),
            ('○ = 해당 안에서 수용.',
             '○ = 해당 안에서 수용. 괄호는 해당 안에서의 범위를 뜻합니다.')],
}

# B · 통합비교본 마스터 비교표 — {행: {열: 값}}
# A안 보유: 분류체계(2축)·키워드 검색·스킬 내려받기·관리자 콘텐츠 관리·이용 통계 조회
# B안 추가: 설명문서 미리보기·회원가입·즐겨찾기·평점·후기·버전 관리·회원·후기 관리·통계 리포트
MASTER_CELLS = {
    'SFR-002': {2: '○(2축)', 3: '○', 4: '○'},
    'SFR-003': {2: '○(키워드)', 3: '○', 4: '○'},
    'SFR-007': {2: '—', 3: '○', 4: '○'},
    'SFR-008': {2: '—', 3: '○', 4: '○'},
    'SFR-009': {2: '—', 3: '○', 4: '○'},
    'SFR-010': {2: '—', 3: '○', 4: '○'},
    'SFR-011': {2: '○', 3: '○', 4: '○'},
    'SFR-012': {2: '○', 3: '○', 4: '○'},
    'SFR-013': {2: '—', 3: '○', 4: '○'},
    'SFR-014': {2: '○(이용 통계)', 3: '○', 4: '○'},
}

NOTICE = '공지사항·이용안내'
BODY_B = ('· 공지사항 등록·게시와 이용안내 정적 페이지를 제공하고, '
          '개인정보·저작권 유의 기준을 상시 게시한다(SFR-013).')
BODY_C = ('· 공지사항 등록·게시와 이용안내 정적 페이지를 제공하고, '
          '개인정보·저작권 유의 기준을 상시 게시한다(SFR-015).')
ANCHOR_B = '· 조회·다운로드·평점 통계 리포트를 제공하고 엑셀로 내려받는다(SFR-012).'
# 문서 안의 인용부호는 ASCII U+0027 이다(활자체 ‘’ 아님) — 확인 후 그대로 쓴다
ANCHOR_C = ("· '결과 없음 검색어' 목록을 스킬 제작 후보로 연결해 "
            "유지관리 기간의 콘텐츠 갱신 우선순위를 데이터로 정한다.")


def out_path(tag):
    return P(os.path.splitext(SRC[tag])[0] + '_교정.docx')


def fix(tag):
    src, dst = P(SRC[tag]), out_path(tag)
    if os.path.abspath(src) == os.path.abspath(dst):
        raise OpError('원본 덮어쓰기 시도')
    shutil.copy2(src, dst)
    _log('== %s  %s' % (tag, os.path.basename(dst)))

    if tag == 'ALL':
        # 표 먼저 (행 삽입 → 개수 문구 치환 순서를 맞춘다)
        for row, vals in MASTER_CELLS.items():
            set_cells(dst, '요구사항 ID', row, vals)
        insert_row_after(dst, '요구사항 ID', 'SFR-014',
                         ['SFR-015', NOTICE, '○', '○', '○'])
    elif tag == 'B':
        insert_row_after(dst, '요구사항 ID', 'SFR-012',
                         ['SFR-013', NOTICE, '수용', 'Ⅲ-2 기능 구현방안'])
        insert_para_after(dst, ANCHOR_B, BODY_B)
    elif tag == 'C':
        insert_row_after(dst, '요구사항 ID', 'SFR-014',
                         ['SFR-015', NOTICE, '수용', 'Ⅲ-2 기능 구현방안'])
        insert_para_after(dst, ANCHOR_C, BODY_C)

    replace(dst, TEXT_FIX[tag])
    return dst


EXPECT_ROWS = {'A': 0, 'B': 1, 'C': 1, 'ALL': 1}


def verify(tag):
    src, dst = P(SRC[tag]), out_path(tag)
    st, sr = table_stats(src)
    dt, dr = table_stats(dst)
    _log('-- %s 검증' % tag)
    _log('   표 %d -> %d (변화 %+d, 기대 0) | 행 %d -> %d (변화 %+d, 기대 %+d)'
         % (st, dt, dt - st, sr, dr, dr - sr, EXPECT_ROWS[tag]))
    if dt != st or dr - sr != EXPECT_ROWS[tag]:
        raise OpError('%s 표/행 개수 이상' % tag)

    ch = diff_blocks(src, dst)
    _log('   텍스트 차이 블록 %d개' % len(ch))
    for kind, a, b in ch:
        for x in a:
            _log('     - %s' % x)
        for x in b:
            _log('     + %s' % x)
    return ch


def main():
    tags = ['A', 'B', 'C', 'ALL']
    if '--verify' not in sys.argv:
        for t in tags:
            fix(t)
    for t in tags:
        verify(t)
    _log('완료 — 교정본 4종')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
