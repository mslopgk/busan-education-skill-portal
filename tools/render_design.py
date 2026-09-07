# -*- coding: utf-8 -*-
"""assets/design/<name>.html -> assets/design/<name>.png
   1280 CSS px 폭을 2배 배율로 찍는다(출력 2560px). 높이는 CSS px 로 지정.
     python tools/render_design.py <name> <height_css>
"""
import os, subprocess, sys
ROOT=os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
D=os.path.join(ROOT,'assets','design')
CHROME=r'C:\Program Files\Google\Chrome\Application\chrome.exe'
name,h=sys.argv[1],int(sys.argv[2])
src=os.path.join(D,name+'.html'); dst=os.path.join(D,name+'.png')
if not os.path.exists(src): raise SystemExit('no html: '+src)
if os.path.exists(dst): os.remove(dst)
subprocess.run([CHROME,'--headless','--disable-gpu','--hide-scrollbars',
 '--force-device-scale-factor=2','--virtual-time-budget=15000',
 '--window-size=1280,%d'%h,'--screenshot='+dst,
 'http://127.0.0.1:8778/%s.html'%name],capture_output=True)
if not os.path.exists(dst): raise SystemExit('chrome failed')
try:
    from PIL import Image
    im=Image.open(dst); w,hh=im.size; px=im.convert('RGB').load()
    bg=px[w-3,hh-3]; y=hh-1
    while y>100 and all(px[x,y]==bg for x in range(0,w,7)): y-=1
    slack=(hh-y)//2
    print('%s  %dx%d  %.0fKB%s'%(name,w,hh,os.path.getsize(dst)/1024,
      '   <- 아래 %dpx(CSS) 공백, 높이를 %d 로'%(slack,(y//2)+24) if slack>60 else ''))
except Exception:
    print('%s  %.0fKB'%(name,os.path.getsize(dst)/1024))
