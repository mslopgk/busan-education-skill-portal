# -*- coding: utf-8 -*-
"""보강한 .docx 를 실제 Microsoft Word 로 PDF 변환하고 페이지를 PNG 로 뽑는다.
Word 가 열어서 리페어 없이 출력된다는 것 자체가 파일 정합성의 증거다.

  python tools/preview.py proposals/xxx_보강.docx            # 전체 페이지 정보 + 처음 6쪽
  python tools/preview.py proposals/xxx_보강.docx 3 7 12     # 지정 페이지만
"""
import os, sys, glob

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OUT = os.path.join(ROOT, 'assets', 'preview')


def to_pdf(docx):
    import win32com.client as win32
    docx = os.path.abspath(docx)
    pdf = os.path.splitext(docx)[0] + '.pdf'
    if os.path.exists(pdf):
        os.remove(pdf)
    word = win32.DispatchEx('Word.Application')
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(docx, ReadOnly=True, AddToRecentFiles=False)
        try:
            doc.ExportAsFixedFormat(pdf, 17)          # 17 = wdExportFormatPDF
            info = (doc.ComputeStatistics(2), doc.Tables.Count,
                    doc.InlineShapes.Count + doc.Shapes.Count)   # 2 = wdStatisticPages
        finally:
            doc.Close(False)
    finally:
        word.Quit()
    return pdf, info


def render(pdf, pages, tag):
    import fitz
    d = fitz.open(pdf)
    os.makedirs(OUT, exist_ok=True)
    made = []
    for p in pages:
        if p < 1 or p > d.page_count:
            continue
        pm = d[p - 1].get_pixmap(dpi=110)
        f = os.path.join(OUT, '%s_p%02d.png' % (tag, p))
        pm.save(f)
        made.append(f)
    n = d.page_count
    d.close()
    return made, n


if __name__ == '__main__':
    src = sys.argv[1]
    want = [int(x) for x in sys.argv[2:]]
    tag = os.path.splitext(os.path.basename(src))[0][:14]
    pdf, (pages, tables, shapes) = to_pdf(src)
    if not want:
        want = list(range(1, min(pages, 6) + 1))
    made, n = render(pdf, want, tag)
    print('%s\n  Word 출력 OK — %d쪽 · 표 %d개 · 그림 %d개\n  PDF %s'
          % (os.path.basename(src), pages, tables, shapes, os.path.basename(pdf)))
    for f in made:
        print('  ' + f)
