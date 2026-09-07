# -*- coding: utf-8 -*-
"""제안서 4종 보강 — placement.json + tables.json + 실사진 + Stitch 화면을 합쳐
docx_augment 로 삽입한다.

  python tools/build_ops.py            # 4종 전부
  python tools/build_ops.py A B        # 일부만

원칙
  · 기존 본문 텍스트는 한 글자도 건드리지 않는다. 새 문단/표만 끼워 넣는다.
  · 기존 [그림 N] 번호를 바꾸는 것도 '내용 수정'이므로, 신규 이미지는
    [사진 N] · [화면 N] 별도 계열로 번호를 매긴다. 표는 tables.json 의 제목을 그대로 쓴다.
  · 번호는 문서 내 실제 등장 순서대로 매긴다(placement.json 작성 순서가 아니라
    앵커 문단의 위치를 기준으로 정렬).
"""
import io, json, os, sys, zipfile
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from docx_augment import augment, verify              # noqa: E402
from swap_figures import swap as swap_figures         # noqa: E402

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
A = lambda *p: os.path.join(ROOT, 'assets', *p)
P = lambda *p: os.path.join(ROOT, 'proposals', *p)

SCREEN_PNG = {
    'A-main': 'A-main', 'A-detail': 'A-detail', 'A-admin': 'A-admin',
    'B-main': 'B-main', 'B-detail': 'B-detail', 'B-admin': 'B-admin',
    'C-search': 'C-search', 'C-tryout': 'C-tryout', 'C-admin': 'C-admin',
    # 융합 세트 — 접근성·반응형은 A안(아카이브)판과 B·C안(포털)판을 따로 쓴다
    'accessibility': 's-a11y-archive', 'accessibility-portal': 's-a11y-portal',
    'responsive': 's-resp-archive',    'responsive-portal': 's-resp-portal',
    'compare': 's-compare',
    'gallery': 'gallery',
}

# A·B·C 는 함께 제출될 수 있으므로 같은 카테고리라도 문서마다 다른 컷을 쓴다.
# 카테고리별로 최소 3장을 확보해 두었으므로 pool[offset] 이 항상 존재한다.
PHOTO_OFFSET = {'A': 0, 'B': 1, 'C': 2, 'ALL': 0}

# 실사진 폭 — 13cm 는 뒤따르는 표의 머리글 행을 고립시켰다.
# 통합비교본은 절(節)이 짧아 11cm 사진이 자꾸 단독 페이지를 만들어 더 줄인다.
# 기존 [그림 N] 을 신규 캡처로 교체한다(작성자 승인). 캡션·본문은 그대로 두고 이미지만 바꾼다.
# 기존 그림에는 검토의견 §10 의 결함이 있다 — A안 그림 7·8 은 서비스명이 '포털'이고 없는
# 활용도구 축이 있으며, C안 그림 6 은 "90% 이상 일치"라면서 84% 카드를 보여주고,
# 관리자 화면 날짜가 2024년이며 부서명이 제각각이다.
FIGURE_SWAP = {
    # 추진 방향(D7+D9+D12 융합) 한 벌로 교체. 앞서 Stitch 판본을 썼다가 규칙 이탈이 확인되어
    # 전부 손작업 산출물로 대체했다 — Stitch 는 지정 수치·문구를 임의로 바꾸고 금지 구조로 회귀했다.
    'A':   {6: 's-a-main',   7: 's-a-detail', 8: 's-a-admin'},
    'B':   {6: 's-b-main',   7: 's-b-detail', 8: 's-b-admin'},
    'C':   {6: 's-c-search', 7: 's-c-tryout', 8: 's-c-admin'},
    # 통합비교본은 같은 화면을 그림 3·5·7 로 재사용한다 — 함께 제출되므로 같이 맞춘다
    'ALL': {3: 's-a-main',   5: 's-b-main',   7: 's-c-search'},
}

PHOTO_CM      = 11.0
PHOTO_CM_DOC  = {'ALL': 9.0}
SCREEN_CM_MAX = 15.5     # 화면 캡처 최대 폭
SCREEN_H_MAX  = 21.0     # 화면 캡처 최대 높이 (A4 본문 높이 안에 들어가게)


def png_size(path):
    with open(path, 'rb') as f:
        d = f.read(33)
    assert d[:8] == b'\x89PNG\r\n\x1a\n', path
    return int.from_bytes(d[16:20], 'big'), int.from_bytes(d[20:24], 'big')


def jpeg_size(path):
    """PIL 없이 SOF 마커에서 크기를 읽는다."""
    with open(path, 'rb') as f:
        d = f.read()
    i = 2
    while i < len(d) - 9:
        if d[i] != 0xFF:
            i += 1; continue
        m = d[i + 1]
        if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(d[i + 7:i + 9], 'big'), int.from_bytes(d[i + 5:i + 7], 'big')
        i += 2 + int.from_bytes(d[i + 2:i + 4], 'big')
    raise ValueError('no SOF in ' + path)


def para_index(docx_path):
    """본문 최상위 문단 텍스트 목록 — 앵커 위치 정렬에 쓴다."""
    root = ET.fromstring(zipfile.ZipFile(docx_path).read('word/document.xml'))
    out, i = [], 0
    for ch in root.find(W + 'body'):
        if ch.tag == W + 'p':
            out.append((i, ''.join((n.text or '') for n in ch.iter(W + 't')).strip()))
        i += 1
    return out


def pos_of(paras, anchor):
    key = ' '.join(anchor.split())[:38]
    hits = [i for i, t in paras if ' '.join(t.split()).startswith(key)]
    if len(hits) != 1:
        raise SystemExit('앵커 %d건 매치: %r' % (len(hits), anchor[:50]))
    return hits[0]


def build(tag):
    plan   = json.load(io.open(A('placement.json'), encoding='utf-8'))[tag]
    photos = json.load(io.open(A('photos.json'), encoding='utf-8'))
    tables = [t for t in json.load(io.open(A('tables.json'), encoding='utf-8')) if t['doc'] == tag]
    src    = P(plan['_doc'])
    paras  = para_index(src)

    by_cat = {}
    for p in photos:
        if '[사용 보류]' in p.get('desc', ''):      # 전수 감사에서 실격된 컷은 제외
            continue
        by_cat.setdefault(p['category'], []).append(p['file'])
    off = PHOTO_OFFSET.get(tag, 0)
    photo_cm = PHOTO_CM_DOC.get(tag, PHOTO_CM)

    # 문서 내 실제 순서로 정렬한 뒤 번호를 매긴다
    slots = sorted(plan['slots'], key=lambda s: pos_of(paras, s['anchor']))
    used, ops = {}, []
    n_photo = n_screen = 0

    for s in slots:
        if s['type'] == 'photo':
            cat = s['category']
            pool = by_cat.get(cat)
            if not pool:
                raise SystemExit('사진 카테고리 없음: %s' % cat)
            k = used.get(cat, 0); used[cat] = k + 1        # 문서 안에서 같은 사진 반복 회피
            fn = pool[(off + k) % len(pool)]
            path = A('photos', fn)
            w, h = jpeg_size(path)
            n_photo += 1
            ops.append({'type': 'image', 'anchor': s['anchor'], 'path': path,
                        'caption': '[사진 %d] %s (참고 이미지)' % (n_photo, s['caption']),
                        'width_cm': photo_cm,
                        'after_table': s.get('after_table', None)})
        else:
            png = SCREEN_PNG[s['key']]
            path = A('stitch', png + '.png')
            if not os.path.exists(path):
                raise SystemExit('화면 이미지 없음: %s' % path)
            w, h = png_size(path)
            cm = min(SCREEN_CM_MAX, SCREEN_H_MAX / (h / float(w)))
            n_screen += 1
            ops.append({'type': 'image', 'anchor': s['anchor'], 'path': path,
                        'caption': '[화면 %d] %s' % (n_screen, s['caption']),
                        'width_cm': round(cm, 2),
                        'after_table': s.get('after_table', None)})

    for t in tables:
        ops.append({'type': 'table', 'anchor': t['anchor'], 'title': t['title'],
                    'columns': t['columns'], 'rows': t['rows']})

    dst = P(os.path.splitext(plan['_doc'])[0] + '_보강.docx')
    augment(src, dst, ops)
    r = verify(src, dst, quiet=True)
    swap = {n: A('stitch', f + '.png') for n, f in FIGURE_SWAP.get(tag, {}).items()}
    swap_log = swap_figures(dst, swap) if swap else []
    print('%-4s %s' % (tag, os.path.basename(dst)))
    print('     사진 %d · 화면 %d · 표 %d   (총 %d개 삽입)'
          % (n_photo, n_screen, len(tables), len(ops)))
    print('     본문 보존 %s | 문자 %s -> %s'
          % ('OK' if r.get('text_preserved', True) else '실패',
             r.get('src_chars', '?'), r.get('dst_chars', '?')))
    for line in swap_log:
        print('   교체' + line)
    return dst


if __name__ == '__main__':
    for tag in (sys.argv[1:] or ['A', 'B', 'C', 'ALL']):
        build(tag)
