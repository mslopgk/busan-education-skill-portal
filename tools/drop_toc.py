# -*- coding: utf-8 -*-
"""목차를 통째로 제거한다.

4종 모두 구조가 같다:
    <w:p> … <w:br w:type="page"/> </w:p>     ← 목차 앞 페이지 나눔
    <w:p> 목  차 </w:p>
    <w:p> [TOC 필드] </w:p>                   ← ※ 안내문은 이 필드의 캐시된 결과
    <w:p> … <w:br w:type="page"/> </w:p>     ← 목차 뒤 페이지 나눔

TOC 필드가 갱신되지 않아 목차 자리가 안내문 한 줄만 있는 빈 쪽으로 출력된다.
목차 제목·필드 문단을 지우고, 앞뒤 페이지 나눔 중 하나만 남긴다(다음 절은 새 쪽에서 시작).

  python tools/drop_toc.py <docx> [...]      # → <이름>_무목차.docx
"""
import os, re, shutil, sys, zipfile

PBREAK = re.compile(r'w:type="page"')


def paras(xml):
    """본문 최상위 <w:p>/<w:tbl> 를 (start, end, kind) 로 잘라낸다."""
    body_s = xml.index('<w:body>') + len('<w:body>')
    body_e = xml.rindex('</w:body>')
    out = []
    for m in re.finditer(r'<w:(p|tbl)(?: [^>]*)?>.*?</w:\1>|<w:p(?: [^>]*)?/>',
                         xml[body_s:body_e], re.S):
        out.append((body_s + m.start(), body_s + m.end(), m.group(1)))
    return out


def text_of(seg):
    return re.sub(r'\s+', ' ', ''.join(re.findall(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', seg, re.S))).strip()


def drop(src, dst=None):
    z = zipfile.ZipFile(src)
    xml = z.read('word/document.xml').decode('utf-8')
    P = paras(xml)

    # 목차 제목 문단
    i_title = None
    for i, (s, e, k) in enumerate(P):
        if k == 'p' and re.fullmatch(r'목\s*차', text_of(xml[s:e])):
            i_title = i
            break
    if i_title is None:
        raise SystemExit('%s: 목차 제목 문단을 찾지 못했다' % os.path.basename(src))

    # 그 뒤에서 TOC 필드를 담은 문단
    i_field = None
    for i in range(i_title + 1, min(i_title + 4, len(P))):
        s, e, k = P[i]
        if k == 'p' and 'TOC' in xml[s:e] and 'instrText' in xml[s:e]:
            i_field = i
            break
    if i_field is None:
        raise SystemExit('%s: TOC 필드 문단을 찾지 못했다' % os.path.basename(src))

    rm = list(range(i_title, i_field + 1))

    # 앞쪽에 페이지 나눔만 든 문단이 있으면 그것도 지운다(뒤쪽 나눔을 남긴다)
    j = i_title - 1
    if j >= 0:
        s, e, k = P[j]
        seg = xml[s:e]
        if k == 'p' and PBREAK.search(seg) and not text_of(seg):
            rm.insert(0, j)

    removed = [(text_of(xml[P[i][0]:P[i][1]]) or '(페이지 나눔)') for i in rm]
    # 뒤에서부터 잘라낸다
    for i in sorted(rm, reverse=True):
        s, e, _ = P[i]
        xml = xml[:s] + xml[e:]

    dst = dst or (os.path.splitext(src)[0] + '_무목차.docx')
    tmp = dst + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as out:
        for it in z.infolist():
            out.writestr(it, xml.encode('utf-8') if it.filename == 'word/document.xml' else z.read(it.filename))
    z.close()
    shutil.move(tmp, dst)
    return dst, removed


if __name__ == '__main__':
    for src in sys.argv[1:]:
        dst, removed = drop(src)
        print('%s' % os.path.basename(dst))
        for t in removed:
            print('   제거: %s' % t[:60])
