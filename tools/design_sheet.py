# -*- coding: utf-8 -*-
"""assets/design/d*.png 을 비교 시트로 묶는다.
상단 일정 높이만 잘라(첫인상 비교) 균일 폭으로 나란히 놓고, 라벨을 얹는다.
  python tools/design_sheet.py [열수]
"""
import glob, os, sys, math
from PIL import Image, ImageDraw

ROOT=os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
D=os.path.join(ROOT,'assets','design')
NAMES={
 'd01-editorial-serif':'D1 편집형 인덱스', 'd02-dark-precision':'D2 다크 정밀',
 'd03-brutalist':'D3 브루탈리스트', 'd04-hangul-poster':'D4 한글 포스터',
 'd05-quiet-minimal':'D5 정적 미니멀', 'd06-catalog-mono':'D6 카탈로그 모노',
 'd07-app-shell':'D7 도구형 앱셸', 'd08-magazine':'D8 잡지 비대칭',
 'd09-data-table':'D9 표 인덱스', 'd10-warm-grain':'D10 웜 그레인',
 'd11-split':'D11 분할 캔버스', 'd12-modern-institution':'D12 신관공서',
}
CW, CROP_RATIO = 620, 1.30      # 셀 폭, 상단 크롭 비율(높이/폭)
cols=int(sys.argv[1]) if len(sys.argv)>1 else 3

files=sorted(p for p in glob.glob(os.path.join(D,'d*.png')))
if not files: raise SystemExit('아직 렌더된 시안이 없다')
ch=int(CW*CROP_RATIO); lab=30
rows=math.ceil(len(files)/cols)
sheet=Image.new('RGB',(cols*(CW+12)+12, rows*(ch+lab+16)+12),'#111111')
d=ImageDraw.Draw(sheet)
for i,p in enumerate(files):
    key=os.path.splitext(os.path.basename(p))[0]
    im=Image.open(p).convert('RGB')
    w,h=im.size
    top=im.crop((0,0,w,min(h,int(w*CROP_RATIO))))
    top=top.resize((CW,int(top.height*CW/top.width)), Image.LANCZOS)
    if top.height>ch: top=top.crop((0,0,CW,ch))
    x=(i%cols)*(CW+12)+12; y=(i//cols)*(ch+lab+16)+12
    d.text((x+2,y+8), NAMES.get(key,key), fill='#EEEEEE')
    sheet.paste(top,(x,y+lab))
    d.rectangle([x-1,y+lab-1,x+CW,y+lab+top.height], outline='#3A3A3A')
out=os.path.join(ROOT,'assets','preview','_design_sheet.png')
sheet.save(out)
print('%s  %dx%d  시안 %d종'%(out,sheet.size[0],sheet.size[1],len(files)))
for p in files: print('  '+os.path.basename(p))
