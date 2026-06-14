# Contents Curator — SPEC

개인용 콘텐츠 큐레이션 앱. 빅테크 추천 알고리즘을 벗어나 직접 선택한 소스와 AI 에이전트가 자율 탐색한 소스에서만 콘텐츠를 수집·요약해 매일 읽을 수 있도록 한다.

---

## 1. 전체 아키텍처


```
PC (Windows, 항상 켜짐)
├── Curator Agent (Python)
│   ├── 스케줄러 (APScheduler)
│   ├── 스크래퍼 (RSS/API + Playwright)
│   ├── LLM (Ollama + OpenRouter)
│   └── Obsidian Vault 기록 (Area/articles/*.md)
│
├── FastAPI JSON 서버
│   └── Tailscale → 안드로이드 앱/위젯
│
└── Obsidian Sync → 모바일 Obsidian 앱 (아카이빙)

안드로이드 앱 (Kotlin + Jetpack Compose)
├── 탭 1: 아티클 목록 (기본 탭)
├── 탭 2: 구독 관리
├── 탭 3: 에이전트 채팅
├── Room DB (읽음 상태)
└── WorkManager (1시간 폴링)

홈 위젯 (Jetpack Glance)
└── 미읽음 아이템 2×3 그리드
```

---

## 2. PC 백엔드

### 2-1. 기술 스택

| 구성요소 | 기술 |
|---|---|
| 언어 | Python |
| API 서버 | FastAPI |
| 스크래핑 | Playwright (LinkedIn, X), RSS 파싱, YouTube Data API |
| LLM — 요약 | Ollama (Llama 3.1 8B, 로컬) |
| LLM — 탐색 | OpenRouter 무료 tier (Llama 3.3 70B 등) |
| 스케줄러 | APScheduler |
| 네트워크 | Tailscale |

### 2-2. 스케줄링

에이전트는 아래 시간대에만 GPU를 사용한다. 하루 10개 Item 할당량이 채워지면 해당 시간대 안이라도 즉시 중단한다.

- 새벽 03:00 ~ 07:00 (매일)
- 평일 10:00 ~ 15:00

### 2-3. 수집 비율

- 구독 소스 (Subscription): 하루 약 5개
- 자율 탐색 (Discovery): 하루 약 5개

### 2-4. 지원 플랫폼 및 접근 방식

| 플랫폼 | 접근 방식 | 비고 |
|---|---|---|
| YouTube | YouTube Data API v3 + 자막 추출 | 무료 |
| Medium | RSS 피드 | 무료 |
| 뉴스 | RSS 피드 | 무료 |
| Substack | RSS 피드 | 무료 |
| LinkedIn | Playwright 브라우저 자동화 | ToS 리스크 감수, 개인 계정 사용 |
| X (Twitter) | Playwright 브라우저 자동화 | ToS 리스크 감수, 개인 계정 사용 |
| Threads | Playwright 브라우저 자동화 | 불안정 허용 |

### 2-5. LLM 역할 분담

| 작업 | 모델 | 이유 |
|---|---|---|
| 영상 트랜스크립트 요약 | Ollama Llama 3.1 8B | 빈번, 단순 요약, rate limit 없음 |
| 아티클 제목 생성 (제목 없는 경우) | Ollama Llama 3.1 8B | 동일 |
| 채널/계정 탐색 및 분석 | OpenRouter 무료 tier | 복잡한 멀티스텝 추론, 가끔만 실행 |

### 2-6. Obsidian Vault .md 구조

경로: `Area/articles/<slug>.md`

```markdown
---
title: "제목 (없으면 AI 생성)"
platform: youtube | linkedin | x | medium | news | threads | substack
source_url: "https://..."
author: "채널명 또는 계정명"
date: 2026-05-31
subscription: true | false
---

[영상인 경우: Curator Agent가 생성한 요약문]
[아티클인 경우: 스크래핑한 원문 전체]
```

### 2-7. FastAPI 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| GET | `/feed/today` | 오늘의 Item 10개 반환 |
| GET | `/feed/items` | 전체 Item 목록 (날짜 필터 가능) |
| GET | `/feed/items/{slug}` | 단일 Item 상세 (본문 포함) |
| GET | `/subscriptions` | 구독 목록 반환 |
| POST | `/subscriptions` | 구독 추가 (에이전트 승인 후) |
| DELETE | `/subscriptions/{id}` | 구독 삭제 |
| POST | `/agent/discover` | 탐색 지시 전송 |
| GET | `/agent/status` | 에이전트 현재 상태 |

---

## 3. 안드로이드 앱

### 3-1. 기술 스택

| 구성요소 | 기술 |
|---|---|
| 언어 | Kotlin |
| UI | Jetpack Compose |
| 위젯 | Jetpack Glance |
| 로컬 DB | Room (읽음 상태 저장) |
| HTTP 클라이언트 | Retrofit |
| 백그라운드 동기화 | WorkManager (1시간 간격) |
| 네트워크 | Tailscale VPN |

### 3-2. 화면 구조

```
BottomNavigation
├── 탭 1: 아티클 목록 (기본)
├── 탭 2: 구독 관리
└── 탭 3: 에이전트 채팅
```

#### 탭 1 — 아티클 목록

- 오늘의 Item 최대 10개를 리스트로 표시
- 각 행: 플랫폼 아이콘 + 제목 + author (subscription인 경우) + 읽음/미읽음 표시
- 탭 → 상세 화면: 마크다운 뷰어로 본문 전체 표시 (영상=요약, 아티클=원문)
- 상세 화면 진입 시 자동으로 읽음 처리 (Room DB 업데이트)
- 상세 화면 하단: 원본 URL 열기 버튼 (fallback)

#### 탭 2 — 구독 관리

- 현재 구독 중인 계정/채널 목록
- 각 항목: 플랫폼 아이콘 + 채널명 + 플랫폼
- 구독 삭제 가능
- 신규 구독 추가는 탭 3 채팅을 통해서만

#### 탭 3 — 에이전트 채팅

- 채팅 UI: 사용자 메시지 + 에이전트 응답
- 에이전트 탐색 결과: 채널/계정 카드 (이름, 플랫폼, 콘텐츠 요약) + 구독 승인 버튼
- 승인 시 즉시 구독 목록에 등록 (POST /subscriptions 호출)

### 3-3. 동기화 흐름

```
WorkManager (1시간 간격)
→ GET /feed/today
→ Room DB 업데이트 (새 Item 저장)
→ 위젯 갱신 트리거
```

---

## 4. 홈 위젯

- 프레임워크: Jetpack Glance
- 크기: 2×3 그리드 (6칸)
- 표시 내용: 미읽음 Item 중 최신 6개, 각 칸에 플랫폼 아이콘 + 제목
- 탭 → 앱의 아티클 목록 탭으로 이동
- 갱신: WorkManager와 연동, 최대 1시간 지연

---

## 5. Curator Agent 워크플로우

### Scheduled 수집 (자동)

```
1. 구독 목록 로드
2. 각 Subscription 소스에서 최신 콘텐츠 가져오기
3. 영상: 트랜스크립트 추출 → Ollama 요약
   아티클: 원문 스크래핑
4. 제목 없으면 Ollama로 생성
5. OG slug 생성 → Area/articles/<slug>.md 저장
6. 10개 할당량 도달 시 중단
```

### Discovery (사용자 지시)

```
1. 사용자가 채팅 탭에서 지시 입력
2. OpenRouter LLM이 웹 탐색으로 관련 계정/채널 발굴
3. 각 채널의 콘텐츠 요약 생성
4. 앱 채팅에 결과 카드 표시
5. 사용자 승인 → 구독 목록 등록
6. 이후 Scheduled 수집에서 자동 처리
```

### One-off 수집 (자율 발굴)

```
1. Discovery 과정 중 구독과 무관한 단발성 좋은 글/영상 발견
2. 즉시 스크래핑 → .md 저장 (subscription: false)
```

---

## 6. 데이터 흐름 요약

```
[플랫폼] → [스크래퍼] → [LLM] → [Vault .md] → [FastAPI]
                                      ↓
                              [Obsidian Sync]
                                      ↓
                            [모바일 Obsidian 앱]
                            (아카이빙, 검색)

[FastAPI] → [Tailscale] → [WorkManager] → [Room DB] → [앱 UI]
                                                   → [위젯]
```
