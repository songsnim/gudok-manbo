# 피드 위젯 — Glance 구현 스펙

시안: `mockup.html`. 단위는 dp/sp, 1px = 1dp. 기준 크기는 S25 4×4 ≈ 340×340dp.
원칙: 위젯은 입간판이다. 제목이 주인공이고, 위젯 안에는 읽음 버튼이 없다. 새 색은 넣지 않는다.

## 1. 색 (모두 `ui/theme/Color.kt` 토큰)

| 용도 | 값 | 토큰 |
|---|---|---|
| 패널 배경 | `#121316` | Background |
| 글 썸네일 대체 블록 | `#1E1F22` | Surface |
| 제목 · "피드" · 빈 상태 제목 | `#E3E3E5` | OnBackground |
| 대체 블록 글자 · 빈 상태 보조문 | `#8A8D93` | Outline |
| 채널명 · 미읽음 수 | `#8AB4F8` | Primary |
| 배지 | 인앱 `platformColor` 그대로 | — |

- 위젯 색은 `ColorProvider(Color)`로 고정한다. 앱이 다크 고정이므로 day/night 분기는 두지 않는다.

## 2. 패널

- `GlanceModifier.fillMaxSize().appWidgetBackground().background(#121316)`
  `.cornerRadius(android.R.dimen.system_app_widget_background_radius)` (One UI ≈ 24dp, API31+).
- 패딩: top 10 · bottom 8 · start 16 · end 16(좌우 대칭).
- 그림자, 테두리, 디바이더는 없다.

## 3. 헤더 (높이 32dp)

- `Row(verticalAlignment = CenterVertically)`:
  - 앱 아이콘 20×20 `cornerRadius(6.dp)` → 8dp
  - "피드" 15sp Bold `#E3E3E5` → 4dp
  - 미읽음 **총개수**(5개 상한 아님) 15sp Bold `#8AB4F8`. 0개일 때는 숨긴다.
- 앱 아이콘은 `Image(ImageProvider(R.mipmap.ic_launcher_foreground), contentScale = Crop)`로 그린다.
  - 런처 아이콘은 adaptive(`mipmap-anydpi-v26/ic_launcher.xml`)다. 배경은 `#E1C38D`이고 전경은 동판화 초상 PNG다.
  - RemoteViews에 adaptive XML을 넘기면 마스크 없이 108dp 캔버스 전체가 그려진다. 그래서 배경까지 칠해진 전경 PNG를 직접 쓰고 모서리는 위젯이 깎는다.
  - 시안은 `mipmap-hdpi/ic_launcher.png`를 data URI로 넣었다.
- 헤더 탭 → 앱 피드 탭(`MainActivity`).

## 4. 행

```
Row(fillMaxWidth, height = rowH, CenterVertically, clickable=본문 열기)
 ├ Column(defaultWeight, padding(end=12))
 │  ├ Row(CenterVertically)                                    // 메타 줄 16dp
 │  │  ├ Box(16×16, bg=platformColor, cornerRadius 6, Center)  // 배지
 │  │  │  └ Text 배지글자 7sp Bold #FFFFFF
 │  │  ├ Spacer 6dp
 │  │  └ Text 채널명 11sp Normal #8AB4F8 maxLines=1
 │  ├ Spacer 2dp
 │  └ Text 제목 14sp Medium #E3E3E5 maxLines=titleLines
 └ Thumb 80×45                                                 // 폭 < 300dp면 생략
```

- 중첩 깊이: 패널 Box > Column > 행 Row > Column > 메타 Row > 배지 Box > Text = 7단계(한도 10 이내).
- 행 목록은 `LazyColumn` 대신 `Column`으로 그린다. 최대 5개 고정이고, 컬렉션 fill-in intent가 필요 없다.
- 행 전체가 하나의 클릭 대상이다. 탭 리플은 기본값을 쓴다.
- 제목 열 폭(4×4) = 340 − 16 − 16 − 80 − 12 = **216dp**. ✓ 버튼이 있던 178dp보다 넓고, 2줄에 약 30자가 들어간다.
- Glance에는 SemiBold가 없다. 인앱 15sp SemiBold 대신 14sp Medium을 쓴다.
- Glance TextStyle에는 lineHeight가 없다. 시스템 기본 행간 ≈19dp 기준으로 계산했다.
- 날짜는 생략한다(보이는 5개가 모두 최신이다).

### 배지 — 인앱 `PlatformBadge` 축소판

- 매핑은 `SubscriptionsScreen.platformColor` / `PlatformBadge`를 공용으로 옮겨 재사용한다. 위젯 안의 복제본(`FeedWidget.kt`의 `platformColor`, `platformEmoji`)은 지운다.
- 인앱 20dp/r8/7sp → 위젯 16dp/r6/7sp. 글자는 0.36 비율(5.8sp)로 줄이면 읽히지 않아 인앱과 같은 7sp를 유지한다.

| platform | 색 | 글자 |
|---|---|---|
| youtube | `#FF0000` | ▶ |
| medium | `#3C4043` | M |
| linkedin | `#0A66C2` | in |
| substack | `#FF6719` | S |
| hackernews | `#FF6600` | Y |
| 그 외 | `#888888` | · |

### 썸네일 (80×45dp, 16:9, `cornerRadius(8.dp)` = 인앱 shapes.small)

- YouTube: 인앱 `thumbnailUrl()` 규칙을 그대로 쓴다(`hqdefault.jpg`).
  - 공용 함수로 옮겨 재사용하고, 복제하지 않는다.
  - 비트맵은 갱신 워커에서 내려받는다. 4:3을 가운데 기준 16:9로 crop한 뒤 **240×135px RGB_565**로 줄인다(≈65KB, 5장 ≈ 330KB). slug 키로 `cacheDir`에 캐시한다.
  - `Image(ImageProvider(bitmap), contentScale = Crop)`
- YouTube가 아니거나 비트맵을 못 받으면 대체 블록을 쓴다.
  - `Box(80×45, bg #1E1F22, cornerRadius 8, Center)` + 채널명 첫 글자 18sp Bold `#8A8D93`.
  - 근거: 플랫폼은 배지가 이미 말하므로 블록은 '누가 썼는지'를 보여주고, 색은 실제 영상 썸네일에만 남긴다.

## 5. 크기별 동작 — `SizeMode.Exact` + `LocalSize`

행 수와 행 높이는 실제 높이로 계산한다. 삼성 셀 크기가 런처 설정마다 달라서 고정 breakpoint보다 이쪽이 안전하다.

```
avail      = H - 10(top) - 32(header) - 8(bottom)   // = H - 50
rows       = floor(avail / 58).coerceIn(1, 5)
rowH       = min(80, avail / rows)                   // 남는 높이를 행에 나눠 아래 공백 제거
titleLines = if (rowH >= 78) 3 else 2                // 3줄 = 메타16 + 2 + 19×3 + 여유
thumb      = W >= 300dp                              // 3칸 폭 이하에서는 썸네일 숨김
```

| 크기(≈) | 행 | 행 높이 | 제목 | 썸네일 |
|---|---|---|---|---|
| 4×6 340×450 | 5 | 80 | 3줄 | O |
| **4×4 340×340** | **5** | **58** | **2줄** | O |
| 4×3 340×255 | 3 | 68 | 2줄 | O |
| 4×2 340×170 | 2 | 60 | 2줄 | O |
| 3×2 255×170 | 2 | 60 | 2줄 | X |

- **절충**: 4×4에서 5행 × 3줄을 넣으려면 약 390dp가 필요하다. 쓸 수 있는 높이는 290dp라 3줄은 들어가지 않는다.
  - 행 수(5)를 지키고 대신 제목 열을 넓혔다(178 → 216dp).
  - 3줄은 행 높이가 78dp 이상인 큰 크기에서만 나온다.
- 헤더는 모든 크기에서 유지한다. 잠금화면(keyguard)에서도 같은 공식으로 그린다.

## 6. 빈 상태 (미읽음 0)

- 헤더는 아이콘과 "피드"만 보인다(숫자 없음).
- 본문은 `Column(fillMaxSize, Center)`:
  - "다 읽었어요" 18sp Bold `#E3E3E5` → 4dp
  - "{H}시에 새 글이 와요" 13sp `#8A8D93`
- H는 `/settings` schedule(6·11·17)에서 지금 이후 첫 시각이다. 없으면 "내일 {첫 시각}시에 새 글이 와요".
- schedule은 마지막 갱신 때 캐시한 값을 쓴다. 위젯 렌더 중에는 네트워크를 쓰지 않는다.
- 전체 탭 → 앱 피드.

## 7. 탭 동작 · 갱신

| 대상 | 액션 |
|---|---|
| 행 | `actionStartActivity<MainActivity>(slug 파라미터)` → 본문 화면. 뒤로 가면 피드 |
| 헤더 / 빈 상태 | `actionStartActivity<MainActivity>()` |

- 위젯에는 읽음 처리 기능이 없다.
- 앱에서 읽음 처리할 때(Room 쓰기 지점) `FeedWidget().updateAll(context)`를 호출해 즉시 갱신한다. 그러면 읽은 Item은 빠지고 다음 Item이 올라온다.

## 8. `feed_widget_info.xml`

```xml
android:targetCellWidth="4"  android:targetCellHeight="4"
android:minWidth="250dp"     android:minHeight="170dp"
android:minResizeWidth="250dp" android:minResizeHeight="110dp"
android:resizeMode="horizontal|vertical"
android:widgetCategory="home_screen|keyguard"
android:updatePeriodMillis="3600000"
```

## 9. 하지 않는 것

- 위젯 안 읽음 처리(✓), 커스텀 폰트(시스템 One UI Sans만 씀), 그림자·블러·그라디언트, 디바이더, 날짜 줄, "모두 읽음", Collection 이동, 라이트 테마.

## 10. 구현 후 조정 (2026-10-05, 실기기 5×6 기준)

위 수치는 4×4 시안 기준이다. 실사용은 화면을 꽉 채운 5×6이라 아래로 바꿨다.

- One UI는 큰 위젯을 보고 크기(5×6 ≈ 507×787dp)로 그린 뒤 `hsResizeRatio`(≈0.71)로 축소한다.
  모든 치수를 실제 화면 dp로 정하고 1/ratio 배 해서 인앱과 같은 실제 크기로 보이게 한다.
- 행은 인앱 `FeedItemRow` 그대로: 배지 20 · 채널 아바타 18 · 채널명 11sp / 제목 15sp Bold
  (행 ≥120dp면 3줄, 아니면 2줄) / 날짜 10sp, 행 사이 0.5dp 디바이더.
- 썸네일은 인앱 86dp보다 10% 작은 77dp 높이(16:9), 320×180 비트맵.
- 헤더: 아이콘 24 · "피드" 18sp. 앱 아이콘은 배경이 칠해진 런처 PNG 복사본(`drawable-nodpi/widget_app_icon.png`).
- Glance 세션 중 `update()`는 `provideGlance`를 다시 부르지 않으므로, 데이터는 재구성 안에서
  버전 키(`notifyWidget`)가 바뀔 때마다 다시 읽는다.
