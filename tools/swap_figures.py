# -*- coding: utf-8 -*-
"""기존 [그림 N] 의 이미지를 새 캡처로 교체한다.

캡션 문단([그림 N] …)에서 거슬러 올라가 바로 앞의 그림 문단을 찾고, 그 blip 이 가리키는
word/media/* 파트의 바이트를 새 PNG 로 바꾼 뒤 표시 크기(wp:extent · a:ext)를 새 이미지의
가로세로비에 맞게 다시 계산한다. **캡션 텍스트와 본문은 건드리지 않는다.**

  python tools/swap_figures.py --list <docx>            # 어떤 그림이 어떤 미디어를 쓰는지 확인
  python tools/swap_figures.py <docx> 6=A-main 7=A-detail 8=A-admin
"""
import io, os, re, shutil, sys, zipfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
STITCH = os.path.join(ROOT, 'assets', 'stitch')
EMU_CM = 360000
MAX_W_CM, MAX_H_CM = 15.5, 20.0      # A4 본문 폭 17cm, 캡션까지 한 쪽에 들어가는 높이

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def png_size(p):
    d = open(p, 'rb').read(33)
    assert d[:8] == b'\x89PNG\r\n\x1a\n', p
    return int.from_bytes(d[16:20], 'big'), int.from_bytes(d[20:24], 'big')


def _img_size(data):
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
    i = 2                                              # JPEG SOF
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1; continue
        m = data[i + 1]
        if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
            return (int.from_bytes(data[i + 7:i + 9], 'big'),
                    int.from_bytes(data[i + 5:i + 7], 'big'))
        i += 2 + int.from_bytes(data[i + 2:i + 4], 'big')
    return None, None


def split_paragraphs(xml):
    """<w:p …>…</w:p> 를 원문 그대로 잘라 (start, end, text) 목록으로 돌려준다."""
    out = []
    for m in re.finditer(r'<w:p(?: [^>]*)?>.*?</w:p>|<w:p(?: [^>]*)?/>', xml, re.S):
        seg = m.group(0)
        text = ''.join(re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', seg, re.S))
        text = re.sub(r'<[^>]+>', '', text)
        out.append((m.start(), m.end(), seg, text.strip()))
    return out


def rels_map(z):
    xml = z.read('word/_rels/document.xml.rels').decode('utf-8')
    return {m.group(1): m.group(2) for m in
            re.finditer(r'<Relationship[^>]*Id="([^"]+)"[^>]*Target="([^"]+)"', xml)}


def analyse(docx):
    z = zipfile.ZipFile(docx)
    xml = z.read('word/document.xml').decode('utf-8')
    rels = rels_map(z)
    paras = split_paragraphs(xml)
    figs = []
    for i, (s, e, seg, text) in enumerate(paras):
        m = re.match(r'\[그림\s*(\d+)\]', text)
        if not m:
            continue
        for j in range(i - 1, max(-1, i - 4), -1):          # 캡션 바로 앞의 그림 문단
            blip = re.search(r'<a:blip[^>]*r:embed="([^"]+)"', paras[j][2])
            if not blip:
                continue
            rid = blip.group(1)
            target = rels.get(rid, '')
            part = 'word/' + target.lstrip('/')
            ext = re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"', paras[j][2])
            data = z.read(part)
            pw, ph = _img_size(data)
            figs.append({'num': int(m.group(1)), 'cap': text[:60], 'para': j, 'rid': rid,
                         'part': part, 'px': (pw, ph), 'bytes': len(data),
                         'cx': int(ext.group(1)) if ext else None,
                         'cy': int(ext.group(2)) if ext else None})
            break
    z.close()
    return figs


def swap(docx, mapping, dst=None):
    """mapping: {그림번호: 새 PNG 경로}"""
    figs = {f['num']: f for f in analyse(docx)}
    for n in mapping:
        if n not in figs:
            raise SystemExit('%s: [그림 %d] 을 찾지 못했다' % (os.path.basename(docx), n))

    z = zipfile.ZipFile(docx)
    xml = z.read('word/document.xml').decode('utf-8')
    paras = split_paragraphs(xml)
    parts = {n: z.read(n) for n in z.namelist()}
    log = []

    for num, newpng in sorted(mapping.items()):
        f = figs[num]
        nw, nh = png_size(newpng)
        w_cm = min(MAX_W_CM, MAX_H_CM / (nh / float(nw)))
        cx, cy = int(round(w_cm * EMU_CM)), int(round(w_cm * (nh / float(nw)) * EMU_CM))
        seg = paras[f['para']][2]
        new_seg = re.sub(r'(<wp:extent )cx="\d+" cy="\d+"', r'\1cx="%d" cy="%d"' % (cx, cy), seg)
        new_seg = re.sub(r'(<a:ext )cx="\d+" cy="\d+"', r'\1cx="%d" cy="%d"' % (cx, cy), new_seg)
        xml = xml.replace(seg, new_seg, 1)
        paras[f['para']] = paras[f['para']][:2] + (new_seg, paras[f['para']][3])
        parts[f['part']] = open(newpng, 'rb').read()
        log.append('  [그림 %d] %-14s %sx%s -> %sx%s  %.1f x %.1f cm'
                   % (num, os.path.basename(newpng), f['px'][0], f['px'][1], nw, nh,
                      w_cm, w_cm * nh / float(nw)))
    parts['word/document.xml'] = xml.encode('utf-8')
    z.close()

    dst = dst or docx
    tmp = dst + '.tmp'
    zin = zipfile.ZipFile(docx)
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as out:
        for item in zin.infolist():
            out.writestr(item, parts[item.filename])
    zin.close()
    shutil.move(tmp, dst)
    return log


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == '--list':
        for f in analyse(a[1]):
            print('[그림 %-2d] %-9s %-18s %4sx%-5s %6.1fKB  %s'
                  % (f['num'], f['rid'], os.path.basename(f['part']),
                     f['px'][0], f['px'][1], f['bytes'] / 1024, f['cap']))
    else:
        mp = {}
        for kv in a[1:]:
            k, _, v = kv.partition('=')
            mp[int(k)] = v if os.path.exists(v) else os.path.join(STITCH, v + '.png')
        print(os.path.basename(a[0]))
        for line in swap(a[0], mp):
            print(line)
