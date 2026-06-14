# Contents Curator

개인용 콘텐츠 큐레이션 앱. 빅테크 추천 알고리즘을 벗어나 사용자가 직접 선택한 소스와 AI 에이전트가 자율 탐색한 소스에서만 콘텐츠를 수집·요약해 뉴스레터 형식으로 제공한다.

## Language

**Item**:
사용자에게 전달되는 단일 콘텐츠 단위. 아티클 또는 영상 요약문, 제목, 썸네일, 원본 소스 링크, 플랫폼, 날짜, 읽음 상태를 포함한다.
_Avoid_: content, post, article, card

**Feed**:
하루치 Item 묶음. 하루 10개로 고정되며, PC 백엔드가 수집 완료 시점에 확정된다.
_Avoid_: timeline, stream, newsletter

**Subscription**:
사용자가 승인한 계정 또는 채널. 등록 후 백엔드가 주기적으로 해당 소스의 Item을 자동 수집한다.
_Avoid_: follow, channel, source

**Discovery**:
Curator Agent가 사용자 지시에 따라 새로운 계정·채널을 탐색하거나 일회성으로 좋은 글·영상을 찾아내는 행위. Subscription 등록 전 사용자 승인 단계를 거친다.
_Avoid_: search, crawl, explore

**Curator Agent**:
Discovery와 스크래핑·요약을 수행하는 AI 에이전트. Ollama(로컬 LLM)를 기본으로, 복잡한 탐색 추론에는 OpenRouter 무료 tier를 보조로 사용한다.
_Avoid_: bot, crawler, AI

**Vault**:
모든 Item의 SSOT. 로컬 Windows PC의 Obsidian Vault이며, Item은 `Area/articles/<slug>.md` 경로에 저장된다. frontmatter에 title, platform, source_url, author, date, subscription 필드를 포함한다. 본문은 Item 유형에 따라 다르다: 영상은 Curator Agent가 생성한 요약문, 아티클은 스크래핑한 원문 전체. Obsidian Sync를 통해 모바일 Obsidian 앱으로 아카이빙 용도로 동기화된다.
_Avoid_: database, storage, repository

**Widget**:
안드로이드 홈 화면 컴포넌트. 미읽음 Item 중 최대 6개를 2×3 그리드로 제목과 플랫폼 아이콘으로 표시한다. 제목이 없는 경우 Curator Agent가 생성한다. Jetpack Glance로 구현하며 WorkManager가 1시간 간격으로 갱신한다.
_Avoid_: shortcut, tile
