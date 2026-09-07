# -*- coding: utf-8 -*-
"""표지 뒤 백지 쪽을 없앤다.

원인: 표지 다음에 <w:br w:type="page"/> 만 든 빈 문단이 있는데, 표지 내용이 한 쪽을
넘기면 그 문단이 다음 쪽으로 밀려간 뒤 거기서 나눔을 실행한다. 결과가 백지 한 쪽이다.
(원본 4종 모두 이 상태였다.)

해결: 그 빈 문단을 지우고, 바로 뒤 문단에 <w:pageBreakBefore/> 를 붙인다.
쪽 나눔 효과는 그대로이고 백지만 사라진다. 텍스트는 건드리지 않는다.

  python tools/fix_blankpage.py <docx> [...]   # 제자리 수정
"""
import os, re, shutil, sys, zipfile

PPR_ORDER = ['pStyle', 'keepNext', 'keepLines', 'pageBreakBefore', 'framePr',
             'widowControl', 'numPr', 'suppressLineNumbers', 'pBdr', 'shd',
             'tabs', 'suppressAutoHyphens', 'spacing', 'ind', 'jc']


def paras(xml):
    s = xml.index('<w:body>') + len('<w:body>')
    e = xml.rindex('</w:body>')
    return [(s + m.start(), s + m.end(), m.group(1))
            for m in re.finditer(r'<w:(p|tbl)(?: [^>]*)?>.*?</w:\1>|<w:p(?: [^>]*)?/>',
                                 xml[s:e], re.S)]


def text_of(seg):
    return re.sub(r'\s+', ' ', ''.join(
        re.findall(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', seg, re.S))).strip()


def add_break_before(seg):
    """문단에 <w:pageBreakBefore/> 를 스키마 순서에 맞게 넣는다."""
    if 'pageBreakBefore' in seg:
        return seg
    m = re.search(r'<w:pPr>(.*?)</w:pPr>', seg, re.S)
    if not m:                                     # pPr 자체가 없으면 새로 만든다
        return re.sub(r'(<w:p(?: [^>]*)?>)', r'\1<w:pPr><w:pageBreakBefore/></w:pPr>', seg, count=1)
    inner = m.group(1)
    idx = PPR_ORDER.index('pageBreakBefore')
    pos = len(inner)                              # 기본은 맨 끝
    for tag in PPR_ORDER[idx + 1:]:
        t = re.search(r'<w:%s\b' % tag, inner)
        if t:
            pos = t.start()
            break
    new = inner[:pos] + '<w:pageBreakBefore/>' + inner[pos:]
    return seg[:m.start(1)] + new + seg[m.end(1):]


def fix(src):
    z = zipfile.ZipFile(src)
    xml = z.read('word/document.xml').decode('utf-8')
    P = paras(xml)

    target = None
    for i, (s, e, k) in enumerate(P[:12]):        # 표지 직후 구간만 본다
        seg = xml[s:e]
        if k == 'p' and 'w:type="page"' in seg and not text_of(seg) and i + 1 < len(P):
            if P[i + 1][2] == 'p':
                target = i
                break
    if target is None:
        z.close()
        return None, '해당 패턴 없음'

    bs, be, _ = P[target]
    ns, ne, _ = P[target + 1]
    nxt = add_break_before(xml[ns:ne])
    after = text_of(nxt)[:40]
    # 빈 나눔 문단(bs~be)을 지우고, 다음 문단(ns~ne)을 pageBreakBefore 붙인 것으로 교체
    xml = xml[:bs] + xml[be:ns] + nxt + xml[ne:]

    tmp = src + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as out:
        for it in z.infolist():
            out.writestr(it, xml.encode('utf-8') if it.filename == 'word/document.xml'
                         else z.read(it.filename))
    z.close()
    shutil.move(tmp, src)
    return after, 'ok'


if __name__ == '__main__':
    for src in sys.argv[1:]:
        after, st = fix(src)
        print('%-58s %s%s' % (os.path.basename(src), st,
                              ('  → 나눔을 「%s」 로 이동' % after) if after else ''))
