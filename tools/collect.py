# -*- coding: utf-8 -*-
"""최종 납품본(docx + pdf)을 한 폴더에 모은다.

  python tools/collect.py <접미사>      # 예: _교정_보강  → deliverable/ 로 수집
  python tools/collect.py --list        # 현재 proposals 안의 파일 계보 확인

파일 계보
  원본            제안서_X안_….docx                     ← 손대지 않음
  내용 교정        제안서_X안_…_교정.docx                 ← 본문 오류 수정
  최종            제안서_X안_…_교정_보강.docx             ← 교정 + 표·사진·화면 보강
수집 시 최종본을 `제안서_X안_…_최종.docx / .pdf` 로 이름을 정리해 담는다.
"""
import os, re, shutil, sys, glob

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
P = os.path.join(ROOT, 'proposals')
OUT = os.path.join(ROOT, 'deliverable')

ORDER = ['_A안_', '_B안_', '_C안_', '_통합비교본_']


def plan_of(name):
    for i, k in enumerate(ORDER):
        if k in name:
            return i
    return 99


def listing():
    rows = []
    for p in sorted(glob.glob(os.path.join(P, '*.docx')) + glob.glob(os.path.join(P, '*.pdf'))):
        b = os.path.basename(p)
        if b.endswith('_교정_보강.docx') or b.endswith('_교정_보강.pdf'): kind = '최종'
        elif b.endswith('_교정.docx') or b.endswith('_교정.pdf'):        kind = '내용 교정'
        elif b.endswith('_보강.docx') or b.endswith('_보강.pdf'):        kind = '보강(교정 전)'
        else:                                                            kind = '원본'
        rows.append((plan_of(b), kind, b, os.path.getsize(p)))
    rows.sort()
    w = max(len(r[2]) for r in rows)
    print('%-14s %-*s %s' % ('구분', w, '파일', '크기'))
    for _, kind, b, sz in rows:
        print('%-14s %-*s %6.1f MB' % (kind, w, b, sz / 1e6))


def collect(suffix):
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    picked = []
    for ext in ('.docx', '.pdf'):
        for p in glob.glob(os.path.join(P, '*' + suffix + ext)):
            b = os.path.basename(p)
            dst = b.replace(suffix + ext, '_최종' + ext)
            shutil.copy2(p, os.path.join(OUT, dst))
            picked.append((plan_of(b), dst, os.path.getsize(p)))
    if not picked:
        raise SystemExit('접미사 %s 에 해당하는 파일이 없다' % suffix)
    picked.sort()
    print('deliverable/ 로 %d개 수집\n' % len(picked))
    w = max(len(n) for _, n, _ in picked)
    for _, n, sz in picked:
        print('  %-*s %6.1f MB' % (w, n, sz / 1e6))
    docs = sum(1 for _, n, _ in picked if n.endswith('.docx'))
    pdfs = sum(1 for _, n, _ in picked if n.endswith('.pdf'))
    print('\ndocx %d개 · pdf %d개' % (docs, pdfs))
    if docs != pdfs:
        print('!! docx 와 pdf 개수가 다르다 — 빠진 쪽을 확인하라')


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == '--list':
        listing()
    else:
        collect(a[0])
