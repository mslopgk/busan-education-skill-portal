# 사진 출처 및 라이선스 (Photo Credits)

부산광역시교육청 교육용 AI 스킬 아카이브/포털 구축 제안서용 사진 자산.

- **출처**: 전량 [Unsplash](https://unsplash.com) 실사 사진 (AI 생성물·일러스트·3D 렌더링 없음)
- **라이선스**: Unsplash License — 상업적 이용 무료, 출처 표기 의무 없음 (Free for commercial use, no attribution required)
  - 참고: <https://unsplash.com/license>
- **다운로드 규격**: `?w=1600&q=80` (가로 1600px, JPEG 품질 80)
- **작가명 비고**: 본 자산은 Unsplash CDN 직접 URL(`images.unsplash.com/photo-<id>`) 로 수집하였으며, CDN 응답에 EXIF/IPTC 작가 메타데이터가 포함되어 있지 않아 개별 작가명을 기계적으로 확정할 수 없었습니다. Unsplash License상 출처 표기 의무가 없으므로 표기를 생략하며, 필요 시 아래 Source URL로 원본을 재확인할 수 있습니다.
- **총 66장** (기존 36장 + 신규 30장) / 전량 JPEG 검증 완료 (`file` 기준), 최소 파일 크기 80KB, 가로 1600px 고정

## 사용 적합성 검수 (원본 해상도 전수 점검)

전 66장을 원본 해상도로 열람하고, 로고 의심 구간은 크롭·확대하여 재확인했습니다. 점검 기준은 ①타사 상표·로고·제품명 노출 ②식별 가능한 미성년자 ③한국어·영어 외 언어 표기 및 외국 기관 표식 ④AI 생성·일러스트·3D 렌더링 ⑤부산 캡션과 상충하는 특정 국가 특정 ⑥신용카드·화폐 등 금융 거래 연상 요소입니다.

기존 36장 중 **18장이 부적합**으로 확인되어 `photos.json`에서 해당 카테고리의 **맨 뒤로 강등**했습니다(파일은 삭제하지 않음). 빌드는 카테고리별 `pool[0]`을 사용하므로 부적합 파일은 선택되지 않습니다. 강등 사유는 `photos.json`의 `desc`에 `[사용 보류]`로 명시했습니다.

| 강등 파일 | 사유 |
|---|---|
| teacher-laptop-3.jpg | 상자에 타사 상표 `MOROCCANOIL` 및 베트남어 문구 노출 |
| teacher-laptop-2.jpg | 노트북 베젤에 `SAMSUNG` 워드마크 판독 |
| training-workshop-1.jpg | 티셔츠의 `Google` 워드마크, 노트북 Apple 로고, 캡션과 불일치 |
| training-workshop-2.jpg | `DELL` 로고 및 `Windows 10` 브랜딩 노출 |
| training-hands-on-1.jpg | 모니터 `Lenovo` 워드마크, 해외 학교 미성년 학생 |
| collaboration-2.jpg | `Sharpie` 마커 로고 및 노트북 Apple 로고 |
| meeting-1.jpg | 노트북 Apple 로고, 6인 구성으로 캡션과 불일치 |
| meeting-3.jpg | 화이트보드 마커의 `EXPO` 상표 근접 판독 |
| documents-2.jpg | 학습지의 `sprintpoint` 로고 및 영문 본문 |
| infra-server-1.jpg | 서버 캐비닛 전면에 `imgIX` 기업 로고 대형 반복 노출 |
| security-1.jpg | 일본어(가나) 각인 키보드 — 국외 환경 특정 |
| security-2.jpg | 신용카드 동반 촬영 — 금융 거래 연상 |
| tablet-2.jpg | 식별 가능한 미성년자 |
| presentation-2.jpg | 실사가 아닌 종이 오려붙임 연출물, 아동 형상 포함 |
| video-recording-2.jpg | 모니터 `HP` 로고 및 포르투갈어 편집 프로그램 UI |
| classroom-1.jpg | 인도 소재 학교로 특정되는 복장·환경 |
| classroom-3.jpg | 태국어 게시물·국왕 초상, 식별 가능한 미성년 학생 |
| school-building-1.jpg | 외국 대학 건물명 `NICANOR REYES HALL` 각인 |

신규 30장은 동일 기준으로 원본 해상도 검수를 통과한 것만 채택했습니다. 검수 과정에서 Apple·Intel·`MacBook Pro`·`hp`·`SAMSUNG` 로고, 러시아어·핀란드어·일본어 화면, 신용카드 동반 컷 등은 후보 단계에서 제외했습니다.

## 신규 추가 파일 (30장)

| filename | unsplash photo id | photographer | source URL | license note |
|---|---|---|---|---|
| busan-city-3.jpg | photo-1702040093537-b8c34eaa0f5c | N/A (CDN 미노출) | https://images.unsplash.com/photo-1702040093537-b8c34eaa0f5c?w=1600&q=80 | Unsplash License — free for commercial use |
| busan-city-4.jpg | photo-1638591752582-45886f5bb0f7 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1638591752582-45886f5bb0f7?w=1600&q=80 | Unsplash License — free for commercial use |
| classroom-4.jpg | photo-1643199121319-b3b5695e4acb | N/A (CDN 미노출) | https://images.unsplash.com/photo-1643199121319-b3b5695e4acb?w=1600&q=80 | Unsplash License — free for commercial use |
| classroom-5.jpg | photo-1738308508484-2a5226b4208d | N/A (CDN 미노출) | https://images.unsplash.com/photo-1738308508484-2a5226b4208d?w=1600&q=80 | Unsplash License — free for commercial use |
| collaboration-3.jpg | photo-1507925921958-8a62f3d1a50d | N/A (CDN 미노출) | https://images.unsplash.com/photo-1507925921958-8a62f3d1a50d?w=1600&q=80 | Unsplash License — free for commercial use |
| collaboration-4.jpg | photo-1562939651-9359f291c988 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1562939651-9359f291c988?w=1600&q=80 | Unsplash License — free for commercial use |
| data-dashboard-3.jpg | photo-1686061592689-312bbfb5c055 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1686061592689-312bbfb5c055?w=1600&q=80 | Unsplash License — free for commercial use |
| documents-3.jpg | photo-1721379805142-faaa28ab1424 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1721379805142-faaa28ab1424?w=1600&q=80 | Unsplash License — free for commercial use |
| documents-4.jpg | photo-1544377193-33dcf4d68fb5 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1544377193-33dcf4d68fb5?w=1600&q=80 | Unsplash License — free for commercial use |
| infra-server-3.jpg | photo-1683322499436-f4383dd59f5a | N/A (CDN 미노출) | https://images.unsplash.com/photo-1683322499436-f4383dd59f5a?w=1600&q=80 | Unsplash License — free for commercial use |
| infra-server-4.jpg | photo-1544197150-b99a580bb7a8 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1544197150-b99a580bb7a8?w=1600&q=80 | Unsplash License — free for commercial use |
| infra-server-5.jpg | photo-1682559736721-c2e77ff4c650 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1682559736721-c2e77ff4c650?w=1600&q=80 | Unsplash License — free for commercial use |
| meeting-6.jpg | photo-1431540015161-0bf868a2d407 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1431540015161-0bf868a2d407?w=1600&q=80 | Unsplash License — free for commercial use |
| presentation-3.jpg | photo-1581091877018-dac6a371d50f | N/A (CDN 미노출) | https://images.unsplash.com/photo-1581091877018-dac6a371d50f?w=1600&q=80 | Unsplash License — free for commercial use |
| presentation-4.jpg | photo-1571826784833-50a3087d9d60 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1571826784833-50a3087d9d60?w=1600&q=80 | Unsplash License — free for commercial use |
| school-building-2.jpg | photo-1721814055224-d7165bf5238b | N/A (CDN 미노출) | https://images.unsplash.com/photo-1721814055224-d7165bf5238b?w=1600&q=80 | Unsplash License — free for commercial use |
| school-building-3.jpg | photo-1731349219592-60ca16964631 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1731349219592-60ca16964631?w=1600&q=80 | Unsplash License — free for commercial use |
| security-3.jpg | photo-1654588831193-0285dab84d5a | N/A (CDN 미노출) | https://images.unsplash.com/photo-1654588831193-0285dab84d5a?w=1600&q=80 | Unsplash License — free for commercial use |
| security-4.jpg | photo-1768839722988-91767bb82b10 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1768839722988-91767bb82b10?w=1600&q=80 | Unsplash License — free for commercial use |
| security-5.jpg | photo-1767972464040-8bfee42d7bed | N/A (CDN 미노출) | https://images.unsplash.com/photo-1767972464040-8bfee42d7bed?w=1600&q=80 | Unsplash License — free for commercial use |
| tablet-3.jpg | photo-1671951483649-d68187142e42 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1671951483649-d68187142e42?w=1600&q=80 | Unsplash License — free for commercial use |
| tablet-4.jpg | photo-1521571942430-b492dedbd302 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1521571942430-b492dedbd302?w=1600&q=80 | Unsplash License — free for commercial use |
| teacher-laptop-4.jpg | photo-1676951592002-e2254ccd337e | N/A (CDN 미노출) | https://images.unsplash.com/photo-1676951592002-e2254ccd337e?w=1600&q=80 | Unsplash License — free for commercial use |
| teacher-laptop-5.jpg | photo-1684125483810-b4c196bc9162 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1684125483810-b4c196bc9162?w=1600&q=80 | Unsplash License — free for commercial use |
| teacher-laptop-6.jpg | photo-1773332598413-a6d5279d1ae8 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1773332598413-a6d5279d1ae8?w=1600&q=80 | Unsplash License — free for commercial use |
| training-hands-on-3.jpg | photo-1678680239675-9b457919b7a8 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1678680239675-9b457919b7a8?w=1600&q=80 | Unsplash License — free for commercial use |
| training-hands-on-4.jpg | photo-1632910121591-29e2484c0259 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1632910121591-29e2484c0259?w=1600&q=80 | Unsplash License — free for commercial use |
| training-workshop-5.jpg | photo-1638957835514-224c57ffe617 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1638957835514-224c57ffe617?w=1600&q=80 | Unsplash License — free for commercial use |
| video-recording-3.jpg | photo-1654723011680-0e037c2a4f18 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1654723011680-0e037c2a4f18?w=1600&q=80 | Unsplash License — free for commercial use |
| video-recording-4.jpg | photo-1625690303837-654c9666d2d0 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1625690303837-654c9666d2d0?w=1600&q=80 | Unsplash License — free for commercial use |

## 기존 파일 (36장)

| filename | unsplash photo id | photographer | source URL | license note |
|---|---|---|---|---|
| busan-city-1.jpg | photo-1625899139925-57f71ba783b4 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1625899139925-57f71ba783b4?w=1600&q=80 | Unsplash License — free for commercial use |
| busan-city-2.jpg | photo-1638591751482-1a7d27fcea15 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1638591751482-1a7d27fcea15?w=1600&q=80 | Unsplash License — free for commercial use |
| classroom-1.jpg | photo-1779358296802-715fc9fbc152 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1779358296802-715fc9fbc152?w=1600&q=80 | Unsplash License — free for commercial use |
| classroom-2.jpg | photo-1594122230689-45899d9e6f69 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1594122230689-45899d9e6f69?w=1600&q=80 | Unsplash License — free for commercial use |
| classroom-3.jpg | photo-1636202339022-7d67f7447e3a | N/A (CDN 미노출) | https://images.unsplash.com/photo-1636202339022-7d67f7447e3a?w=1600&q=80 | Unsplash License — free for commercial use |
| collaboration-1.jpg | photo-1758691736843-90f58dce465e | N/A (CDN 미노출) | https://images.unsplash.com/photo-1758691736843-90f58dce465e?w=1600&q=80 | Unsplash License — free for commercial use |
| collaboration-2.jpg | photo-1571573695320-0f836788538a | N/A (CDN 미노출) | https://images.unsplash.com/photo-1571573695320-0f836788538a?w=1600&q=80 | Unsplash License — free for commercial use |
| data-dashboard-1.jpg | photo-1551288049-bebda4e38f71 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1600&q=80 | Unsplash License — free for commercial use |
| data-dashboard-2.jpg | photo-1526628953301-3e589a6a8b74 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1526628953301-3e589a6a8b74?w=1600&q=80 | Unsplash License — free for commercial use |
| documents-1.jpg | photo-1583521214690-73421a1829a9 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1583521214690-73421a1829a9?w=1600&q=80 | Unsplash License — free for commercial use |
| documents-2.jpg | photo-1631651693480-97f1132e333d | N/A (CDN 미노출) | https://images.unsplash.com/photo-1631651693480-97f1132e333d?w=1600&q=80 | Unsplash License — free for commercial use |
| infra-server-1.jpg | photo-1506399309177-3b43e99fead2 | imgix (추정) | https://images.unsplash.com/photo-1506399309177-3b43e99fead2?w=1600&q=80 | Unsplash License — free for commercial use |
| infra-server-2.jpg | photo-1762163516269-3c143e04175c | N/A (CDN 미노출) | https://images.unsplash.com/photo-1762163516269-3c143e04175c?w=1600&q=80 | Unsplash License — free for commercial use |
| meeting-1.jpg | photo-1731458769726-cef60c792665 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1731458769726-cef60c792665?w=1600&q=80 | Unsplash License — free for commercial use |
| meeting-2.jpg | photo-1758691737278-3af15b37af48 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1758691737278-3af15b37af48?w=1600&q=80 | Unsplash License — free for commercial use |
| meeting-3.jpg | photo-1532622785990-d2c36a76f5a6 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1532622785990-d2c36a76f5a6?w=1600&q=80 | Unsplash License — free for commercial use |
| meeting-4.jpg | photo-1542626991-cbc4e32524cc | N/A (CDN 미노출) | https://images.unsplash.com/photo-1542626991-cbc4e32524cc?w=1600&q=80 | Unsplash License — free for commercial use |
| presentation-1.jpg | photo-1646579886135-068c73800308 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1646579886135-068c73800308?w=1600&q=80 | Unsplash License — free for commercial use |
| presentation-2.jpg | photo-1649920442906-3c8ef428fb6e | N/A (CDN 미노출) | https://images.unsplash.com/photo-1649920442906-3c8ef428fb6e?w=1600&q=80 | Unsplash License — free for commercial use |
| school-building-1.jpg | photo-1613896527026-f195d5c818ed | N/A (CDN 미노출) | https://images.unsplash.com/photo-1613896527026-f195d5c818ed?w=1600&q=80 | Unsplash License — free for commercial use |
| school-corridor-1.jpg | photo-1693600411508-d7e9a9fef63a | N/A (CDN 미노출) | https://images.unsplash.com/photo-1693600411508-d7e9a9fef63a?w=1600&q=80 | Unsplash License — free for commercial use |
| security-1.jpg | photo-1614064641938-3bbee52942c7 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1614064641938-3bbee52942c7?w=1600&q=80 | Unsplash License — free for commercial use |
| security-2.jpg | photo-1633265486064-086b219458ec | N/A (CDN 미노출) | https://images.unsplash.com/photo-1633265486064-086b219458ec?w=1600&q=80 | Unsplash License — free for commercial use |
| tablet-1.jpg | photo-1557825835-70d97c4aa567 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1557825835-70d97c4aa567?w=1600&q=80 | Unsplash License — free for commercial use |
| tablet-2.jpg | photo-1728455635901-bb16530faf40 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1728455635901-bb16530faf40?w=1600&q=80 | Unsplash License — free for commercial use |
| teacher-laptop-1.jpg | photo-1758685848208-e108b6af94cc | N/A (CDN 미노출) | https://images.unsplash.com/photo-1758685848208-e108b6af94cc?w=1600&q=80 | Unsplash License — free for commercial use |
| teacher-laptop-2.jpg | photo-1543270122-f7a11ad44f3a | N/A (CDN 미노출) | https://images.unsplash.com/photo-1543270122-f7a11ad44f3a?w=1600&q=80 | Unsplash License — free for commercial use |
| teacher-laptop-3.jpg | photo-1462356731349-7c52a17674cd | N/A (CDN 미노출) | https://images.unsplash.com/photo-1462356731349-7c52a17674cd?w=1600&q=80 | Unsplash License — free for commercial use |
| training-hands-on-1.jpg | photo-1719159381981-1327b22aff9b | N/A (CDN 미노출) | https://images.unsplash.com/photo-1719159381981-1327b22aff9b?w=1600&q=80 | Unsplash License — free for commercial use |
| training-hands-on-2.jpg | photo-1522071820081-009f0129c71c | Annie Spratt (추정) | https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=1600&q=80 | Unsplash License — free for commercial use |
| training-workshop-1.jpg | photo-1592303637753-ce1e6b8a0ffb | N/A (CDN 미노출) | https://images.unsplash.com/photo-1592303637753-ce1e6b8a0ffb?w=1600&q=80 | Unsplash License — free for commercial use |
| training-workshop-2.jpg | photo-1542744173-8e7e53415bb0 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1542744173-8e7e53415bb0?w=1600&q=80 | Unsplash License — free for commercial use |
| training-workshop-3.jpg | photo-1768448808550-3148cce53a19 | N/A (CDN 미노출) | https://images.unsplash.com/photo-1768448808550-3148cce53a19?w=1600&q=80 | Unsplash License — free for commercial use |
| training-workshop-4.jpg | photo-1503428593586-e225b39bddfe | N/A (CDN 미노출) | https://images.unsplash.com/photo-1503428593586-e225b39bddfe?w=1600&q=80 | Unsplash License — free for commercial use |
| video-recording-1.jpg | photo-1632187981988-40f3cbaeef5e | N/A (CDN 미노출) | https://images.unsplash.com/photo-1632187981988-40f3cbaeef5e?w=1600&q=80 | Unsplash License — free for commercial use |
| video-recording-2.jpg | photo-1749410342681-3510f9edb7ad | N/A (CDN 미노출) | https://images.unsplash.com/photo-1749410342681-3510f9edb7ad?w=1600&q=80 | Unsplash License — free for commercial use |

## 카테고리 슬러그 매핑 (배치 스크립트용)

`photos.json`은 카테고리별로 **좋은 순서대로** 정렬되어 있으며, 빌드는 `pool[0]`(카테고리 첫 항목)을 사용합니다. 아래 표의 순서가 곧 우선순위이고, `[보류]` 표시 파일은 항상 맨 뒤에 있어 선택되지 않습니다. A안/B안/C안 동시 제출 시 각 카테고리에서 1·2·3순위를 나눠 쓰면 문서 간 사진 중복을 피할 수 있습니다(전 카테고리 최소 3장 확보).

| 슬러그 | 1순위 (pool[0]) | 2순위 | 3순위 | 보류 (사용 안 함) |
|---|---|---|---|---|
| `busan-city` | busan-city-3 | busan-city-4 | busan-city-2 | — (busan-city-1은 4순위, 사용 가능) |
| `teacher-laptop` | teacher-laptop-4 | teacher-laptop-1 | teacher-laptop-5 | teacher-laptop-3, teacher-laptop-2 |
| `training-workshop` | training-workshop-3 | training-workshop-5 | training-workshop-4 | training-workshop-1, training-workshop-2 |
| `training-hands-on` | training-hands-on-3 | training-hands-on-4 | training-hands-on-2 | training-hands-on-1 |
| `collaboration` | collaboration-3 | collaboration-1 | collaboration-4 | collaboration-2 |
| `meeting` | meeting-2 | meeting-6 | meeting-4 | meeting-3, meeting-1 |
| `documents` | documents-1 | documents-3 | documents-4 | documents-2 |
| `server-cloud` | infra-server-3 | infra-server-2 | infra-server-4 | infra-server-1 |
| `security` | security-3 | security-4 | security-5 | security-1, security-2 |
| `analytics-screen` | data-dashboard-1 | data-dashboard-3 | data-dashboard-2 | — |
| `tablet` | tablet-3 | tablet-1 | tablet-4 | tablet-2 |
| `presentation` | presentation-3 | presentation-4 | presentation-1 | presentation-2 |
| `video-recording` | video-recording-3 | video-recording-1 | video-recording-4 | video-recording-2 |
| `classroom` | classroom-4 | classroom-2 | classroom-5 | classroom-1, classroom-3 |
| `school-building` | school-building-2 | school-corridor-1 | school-building-3 | school-building-1 |

`teacher-laptop`은 4순위 teacher-laptop-6, `server-cloud`는 4순위 infra-server-5까지 사용 가능합니다.
