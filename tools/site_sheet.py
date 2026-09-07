# -*- coding: utf-8 -*-
"""융합 세트(추진 방향) 화면 전체를 한 장의 비교 시트로 묶는다.
  python tools/site_sheet.py [열수]
"""
import os, sys, math
from PIL import Image, ImageDraw
ROOT=os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
D=os.path.join(ROOT,'assets','design')
SET=[('s-a-main','A안 아카이브 · 메인','손작업'),
     ('s-a-detail','A안 아카이브 · 상세','손작업'),
     ('s-a-admin','A안 아카이브 · 관리자','손작업'),
     ('s-b-main','B안 포털 · 메인','손작업'),
     ('s-b-detail','B안 포털 · 상세','손작업'),
     ('s-b-admin','B안 포털 · 관리자','손작업'),
     ('s-c-search','C안 · AI 자연어 검색','손작업'),
     ('s-c-tryout','C안 · 브라우저 체험','손작업'),
     ('s-c-admin','C안 · 검색어 분석','손작업'),
     ('s-compare','공용 · 3안 비교','손작업'),
     ('s-a11y-archive','공용 · 접근성(아카이브)','손작업'),
     ('s-a11y-portal','공용 · 접근성(포털)','손작업'),
     ('s-resp-archive','공용 · 반응형(아카이브)','손작업'),
     ('s-resp-portal','공용 · 반응형(포털)','손작업'),
     ('gallery','제안서 도판 · 12시안 검토','손작업')]
CW, RATIO, LAB = 600, 1.15, 34
cols=int(sys.argv[1]) if len(sys.argv)>1 else 3
have=[(k,t,s) for k,t,s in SET if os.path.exists(os.path.join(D,k+'.png'))]
if not have: raise SystemExit('아직 없다')
ch=int(CW*RATIO); rows=math.ceil(len(have)/cols)
sh=Image.new('RGB',(cols*(CW+14)+14, rows*(ch+LAB+16)+14),'#101418')
d=ImageDraw.Draw(sh)
for i,(k,t,src) in enumerate(have):
    im=Image.open(os.path.join(D,k+'.png')).convert('RGB'); w,h=im.size
    top=im.crop((0,0,w,min(h,int(w*RATIO))))
    top=top.resize((CW,int(top.height*CW/top.width)),Image.LANCZOS)
    if top.height>ch: top=top.crop((0,0,CW,ch))
    x=(i%cols)*(CW+14)+14; y=(i//cols)*(ch+LAB+16)+14
    d.text((x+2,y+6), t, fill='#F2F5F8')
    d.text((x+2,y+19), '%s · 비율 %.2f'%(src, h/w), fill='#8A97A2')
    sh.paste(top,(x,y+LAB))
    d.rectangle([x-1,y+LAB-1,x+CW,y+LAB+top.height], outline='#2C3540')
out=os.path.join(ROOT,'assets','preview','_site_sheet.png')
sh.save(out)
print('%s  %dx%d  화면 %d종'%(out,sh.size[0],sh.size[1],len(have)))
missing=[k for k,_,_ in SET if not os.path.exists(os.path.join(D,k+'.png'))]
if missing: print('대기:', ', '.join(missing))
