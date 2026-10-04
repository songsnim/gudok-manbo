# 261005-feat-new-items-notification — 새 글 수집되면 잠금화면 알림 한 장

**Blocked by:** `261005-feat-widget-redesign` — 같은 미읽음 목록 API와 동기화 Worker를 재사용한다.

**Status:** ready-for-agent (위젯 티켓 이후)

## What to build

One UI 8.5는 사이드로드 앱의 잠금화면 위젯을 허용하지 않는다. 잠금화면에서 콘텐츠가 눈에
밟히게 하는 현실적인 길은 알림이다.

수집이 끝나 새 Item이 생기면 묶음 알림 한 장을 띄운다. 펼치면 새 글 제목 목록(InboxStyle),
잠금화면에서도 내용이 보이게 공개(`VISIBILITY_PUBLIC`)로 둔다. 탭하면 피드로 간다. 하루 3번
수집이니 최대 3장 — Item마다 알림을 띄우지 않는다.

백엔드에 푸시(FCM)가 없으므로 폰의 동기화 Worker가 처음 보는 slug를 감지해 알림을 띄운다.
수집 직후 몇십 분 지연은 허용한다.

## Acceptance criteria

- [ ] 마지막으로 알린 뒤 새로 생긴 Feed Item이 있을 때만 알림 1장. 없으면 아무것도 안 띄운다.
- [ ] InboxStyle — 제목 줄마다 "채널 · 제목", 요약 줄 "새 글 N개". 같은 알림 ID로 덮어써 쌓이지 않는다.
- [ ] `VISIBILITY_PUBLIC` — 잠금화면에서 내용이 보인다(폰 설정 "알림 내용 표시"가 켜져 있다는 전제).
- [ ] 탭 → 앱 피드 화면.
- [ ] Android 13+ `POST_NOTIFICATIONS` 권한 요청. 거부하면 조용히 넘어간다.
- [ ] 첫 설치·첫 동기화에서는 기존 Item 전체를 "새 글"로 알리지 않는다.
- [ ] 새 slug 판정 로직을 확인하는 검사 하나.
