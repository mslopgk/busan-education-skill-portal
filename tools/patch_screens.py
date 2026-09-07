# -*- coding: utf-8 -*-
"""Stitch 가 export 에 반영하지 못한 수정 사항을 로컬 HTML 에 적용한다.
Stitch edit_screens 는 성공을 반환하지만 export 파일이 갱신되지 않으므로 여기서 직접 고친다."""
import io, os, sys

H = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'stitch', 'html')
H = os.path.normpath(H)

def load(n):  return io.open(os.path.join(H, n), encoding='utf-8').read()
def save(n,s): io.open(os.path.join(H, n), 'w', encoding='utf-8').write(s); return s

def inject(s, js):
    """</body> 직전에 패치 스크립트를 삽입한다."""
    tag = '<script>document.addEventListener("DOMContentLoaded",function(){%s});</script>' % js
    return s.replace('</body>', tag + '\n</body>') if '</body>' in s else s + tag

report = []
def rep(f, what, ok):  report.append((f, what, 'OK' if ok else 'MISS'))

# ─────────────────────────────────────────────────────────────
# A-admin : 이미 문자열 치환 완료 (포털→아카이브, 공지·배너). 검증만.
s = load('A-admin.html')
rep('A-admin', '포털 표기 제거', '포털' not in s)
rep('A-admin', '아카이브 관리 시스템', '아카이브 관리 시스템' in s)
rep('A-admin', '공지·배너 관리', '공지·배너' in s)

# ─────────────────────────────────────────────────────────────
# C-search : ① 사이드바 개수 40종 정합  ② AI 추천 3번째 카드(84%) 추가
s = load('C-search.html')
n0 = s
for old, new in (('rounded-full shadow-sm border border-accent/10">142<',
                  'rounded-full shadow-sm border border-accent/10">10<'),
                 ('border border-border">86<',  'border border-border">9<'),
                 ('border border-border">95<',  'border border-border">6<'),
                 ('border border-border">112<', 'border border-border">7<')):
    s = s.replace(old, new)
rep('C-search', '사이드바 개수 10/9/6/7', s != n0)

js = r'''
 // ① 사이드바에 특수·상담 4 / 학교 실무 4 추가 (합계 40종)
 var ul=document.querySelector('aside ul');
 if(ul && ul.children.length===4){
   [['특수·상담','4'],['학교 실무','4']].forEach(function(p){
     var li=ul.children[3].cloneNode(true), sp=li.querySelectorAll('span');
     sp[0].textContent=p[0]; sp[1].textContent=p[1]; ul.appendChild(li);
   });
 }
 // ② AI 추천 결과 3번째 카드 — 2번 카드를 복제해 텍스트/일치율만 교체
 var grid=document.querySelector('section .grid.grid-cols-1');
 if(grid && grid.children.length===2){
   var c=grid.children[1].cloneNode(true);
   c.querySelector('h3').textContent='서술형 채점 기준표 생성';
   c.querySelector('p').textContent='과학 교과 서술형 문항에 최적화된 부분 점수 산정 기준과 정답 예시를 생성합니다.';
   var reason=c.querySelectorAll('.bg-\\[\\#F0FDF4\\] span');
   if(reason.length>1) reason[1].textContent='AI 추천 이유: 중등 과학 · 평가 유형 일치';
   var stat=c.querySelector('.text-sm.text-muted');
   if(stat) stat.textContent='조회 620 | 사용 355';
   var arc=c.querySelectorAll('svg path');
   if(arc.length>1) arc[1].setAttribute('stroke-dasharray','84, 100');
   var pct=c.querySelector('.text-lg.font-bold');
   if(pct) pct.textContent='84%';
   grid.appendChild(c);
 }
'''
s = inject(s, js)
save('C-search.html', s)
rep('C-search', '3번째 카드 스크립트 주입', 'grid.appendChild(c)' in s)

# ─────────────────────────────────────────────────────────────
# B-admin : 막대그래프가 렌더되지 않음 — 주차 그룹 div 에 높이가 없어 자식의 % 높이가 0 이 된다
s = load('B-admin.html')
old = 'class="flex items-end space-x-2 w-1/4 justify-center relative group"'
cnt = s.count(old)
s = s.replace(old, 'class="flex items-end space-x-2 w-1/4 h-full justify-center relative group"')
save('B-admin.html', s)
rep('B-admin', '막대 그룹 h-full 부여 (%d개)' % cnt, cnt == 4)

# ─────────────────────────────────────────────────────────────
# B-main : 푸터 저작권 한 줄이 영문 → 한국어 (디자인 시스템: 모든 UI 텍스트 한국어)
s = load('B-main.html')
old = 'Copyright © 2026 Busan Metropolitan Office of Education. All rights reserved.'
ok = old in s
s = s.replace(old, 'Copyright © 2026 부산광역시교육청. All Rights Reserved.')
save('B-main.html', s)
rep('B-main', '푸터 한국어화', ok)

# ─────────────────────────────────────────────────────────────
# B-detail : 교직원 전용 고지문이 앰버(경고) 톤 → 회색 보조 톤
#            앰버는 개인정보 경고 전용이므로 고지문에 쓰면 위계가 무너진다
s = load('B-detail.html')
old = 'class="bg-warn-bg text-warn-text p-3 rounded text-xs leading-relaxed border border-[#FDE68A]"'
ok = old in s
s = s.replace(old, 'class="bg-page text-muted p-3 rounded text-xs leading-relaxed border border-border"')
save('B-detail.html', s)
rep('B-detail', '고지문 회색 톤 전환', ok)

# ─────────────────────────────────────────────────────────────
w = max(len(r[0]) for r in report)
print('%-*s  %-28s %s' % (w, 'FILE', 'PATCH', 'RESULT'))
print('-' * (w + 40))
bad = 0
for f, what, res in report:
    print('%-*s  %-28s %s' % (w, f, what, res))
    if res != 'OK': bad += 1
print('\n%d patches, %d not applied' % (len(report), bad))
sys.exit(1 if bad else 0)
