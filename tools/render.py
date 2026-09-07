# -*- coding: utf-8 -*-
"""로컬 HTML 을 헤드리스 Chrome 으로 렌더링한다.

  python tools/render.py C-admin                 # 기본 높이로 렌더
  python tools/render.py C-admin:1200            # 높이(CSS px) 지정
  python tools/render.py --all

전제: assets/stitch/html 을 http://127.0.0.1:8777 로 서빙 중일 것.
      (없으면: cd assets/stitch/html && python -m http.server 8777)
출력: assets/stitch/<name>.png — 1280 CSS px 를 2배 배율로 찍어 2560px 폭 이미지가 나온다.

━━ 반드시 지킬 것 ━━
1) 폭은 1280 CSS px 고정 + `--force-device-scale-factor=2`.
   이 페이지들은 콘텐츠를 max-w-[1280px] 로 가운데 정렬한다. 창을 2560 CSS px 로 열면
   콘텐츠가 화면 절반만 차지하고 좌우에 거대한 여백이 생긴다. 반드시 1280 으로 열고
   배율 2배로 해상도를 확보한다(Stitch 가 스크린샷을 만드는 방식과 동일).
2) 창 높이를 무작정 크게 잡지 말 것. 다수 페이지가 min-h-screen 을 쓰므로 창이 크면
   레이아웃이 늘어나 푸터가 맨 아래로 밀리고 가운데가 텅 빈다.
3) 아래 HEIGHT 는 CSS px 기준이고 출력 PNG 높이는 그 2배다.
   내용을 늘리거나 줄이는 수정을 했으면 값을 갱신하고 결과를 눈으로 확인할 것.
"""
import os, subprocess, sys, glob

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
HTML = os.path.join(ROOT, 'assets', 'stitch', 'html')
OUT  = os.path.join(ROOT, 'assets', 'stitch')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
PORT, CSS_WIDTH, SCALE = 8777, 1280, 2

# CSS px 기준 높이 (출력 PNG 높이 = 이 값 × 2)
HEIGHT = {
    'A-main': 1889, 'A-admin': 1043, 'A-detail': 2193,
    'B-main': 1678, 'B-detail': 1291, 'B-admin': 1150,
    'C-search': 1300, 'C-tryout': 1277, 'C-admin': 960,
    'SH-a11y': 1300, 'SH-compare': 1724, 'SH-responsive': 1024,
    'SH-a11y-portal': 1300, 'SH-responsive-portal': 1024,
}

def render(name, height=None):
    src = os.path.join(HTML, name + '.html')
    if not os.path.exists(src):
        raise SystemExit('no such html: ' + src)
    h = height or HEIGHT.get(name)
    if not h:
        raise SystemExit('%s: 높이를 모른다. name:HEIGHT(CSS px) 형식으로 지정하라.' % name)
    dst = os.path.join(OUT, name + '.png')
    if os.path.exists(dst):
        os.remove(dst)
    r = subprocess.run([CHROME, '--headless', '--disable-gpu', '--hide-scrollbars',
                        '--force-device-scale-factor=%d' % SCALE,
                        '--virtual-time-budget=12000',
                        '--window-size=%d,%d' % (CSS_WIDTH, h), '--screenshot=' + dst,
                        'http://127.0.0.1:%d/%s.html' % (PORT, name)],
                       capture_output=True)
    if not os.path.exists(dst):
        raise SystemExit('chrome 실패 %s: %s' % (name, r.stderr.decode('utf8', 'replace')[-400:]))

    note, dim = '', '?'
    try:
        from PIL import Image
        im = Image.open(dst).convert('RGB'); w, hh = im.size; px = im.load()
        dim = '%dx%d' % (w, hh)
        bg = px[w - 3, hh - 3]
        y = hh - 1
        while y > 100 and all(px[x, y] == bg for x in range(0, w, 7)):
            y -= 1
        slack = (hh - y) // SCALE
        if slack > 60:
            note = '  <- 아래 %dpx(CSS) 공백, 높이를 %d 로' % (slack, (y // SCALE) + 24)
    except Exception:
        pass
    print('%-16s css %4dx%-5d -> %-11s %6.0f KB%s'
          % (name, CSS_WIDTH, h, dim, os.path.getsize(dst) / 1024, note))

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] == '--all':
        args = sorted(os.path.splitext(os.path.basename(p))[0]
                      for p in glob.glob(os.path.join(HTML, '*.html')))
    for a in args:
        n, _, hh = a.partition(':')
        render(n, int(hh) if hh else None)
