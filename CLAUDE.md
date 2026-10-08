# 1. Motivation

- What: 현재 repo 모바일 앱이 달성하고자 하는 목표
  - 구독한 유튜브(혹은 다른 플랫폼) 채널의 영상(혹은 글)만 소비
  - 영상이 아니라 **텍스트**로 요약하여 시청
- Why: 왜 하필 구독만? 왜 하필 텍스트로?
  - 유튜브의 추천 알고리즘은 유튜브에 머무르는 시간을 늘리기 위한 방향으로 학습됨
  - 그러다보니 불건전하거나 영양가없는 고자극 영상 추천이 잦음
  - 유튜브를 아예 삶에서 배제하기엔 유용한 정보가 유튜브에 존재
  - 영상 시청보다 텍스트로 습득하는 지식이 장기 기억이 될 확률이 높음
  - 많은 정보와 지식을 빠르게 소화하기엔 텍스트가 유리

# 2. Context

- 삼성 갤럭시S25 개인 폰에서만 사용하는 용도
- AI 모델을 ollama나 openron

# 3. Language

- Item:  
사용자에게 전달되는 단일 콘텐츠 단위. 아티클 또는 영상 요약문, 제목, 썸네일, 원본 소스 링크, 플랫폼, 날짜, 읽음 상태를 포함한다.  
Avoid: content, post, article, card
- Feed:  
아직 처리하지 않은 Item의 받은편지함. Vault의 articles/ 폴더에 사는 Item 전체를 말한다. 수집일로부터 30일이 지나고 Collection으로 옮겨지지 않은 Item은 자동 삭제된다.  
Avoid: timeline, stream, newsletter
- Collection:  
사용자가 Feed에서 명시적으로 남기기로 선택한 Item. Vault의 collections/ 폴더에 살며 만료되지 않는다. Feed에서 Collection으로의 이동은 파일 이동이며 되돌릴 수 없다 — Collection에서 빼는 것은 완전 삭제다.  
Avoid: bookmark, favorite, saved, archive
- Subscription:  
사용자가 승인한 계정 또는 채널. 등록 후 백엔드가 주기적으로 해당 소스의 Item을 자동 수집한다.  
Avoid: follow, channel, source
- Discovery:  
Curator Agent가 사용자 지시에 따라 새로운 계정·채널을 탐색하거나 일회성으로 좋은 글·영상을 찾아내는 행위. Subscription 등록 전 사용자 승인 단계를 거친다.  
Avoid: search, crawl, explore
- Curator Agent:  
Discovery와 스크래핑·요약을 수행하는 AI 에이전트. OpenRouter 무료 tier 모델의 폴백 체인을 사용한다.  
Avoid: bot, crawler, AI
- Vault:  
모든 Item의 SSOT. 로컬 Windows PC의 Obsidian Vault이며, Item은 $VAULT_PATH/Resource/gudok-manbo/ 아래 두 폴더 — articles/(Feed)와 collections/(Collection) — 에 <제목>-<slug>.md 로 저장된다. 백엔드 운영 데이터(구독 목록, 앱 설정, 실행 로그)는 Vault에 두지 않고 backend/data/에 남으며 모바일로 동기화되지 않는다. frontmatter에 title, platform, source_url, author, date, subscription 필드를 포함한다. tags는 Curator Agent가 저장 시 $VAULT_PATH/CLAUDE.md의 태그 표 안에서 고른다(표가 SSOT, 실패하면 생략). 본문은 Item 유형에 따라 다르다: 영상은 Curator Agent가 생성한 요약문, 아티클은 스크래핑한 원문 전체. Obsidian Sync를 통해 모바일 Obsidian 앱으로 아카이빙 용도로 동기화된다.
Avoid: database, storage, repository
- Widget:  
안드로이드 홈 화면 컴포넌트. 오늘 수집된 Feed Item 전체를 인앱 피드 행과 같은 모양의 스크롤 목록으로 보여준다. 읽은 Item은 목록에 남고 흐리게 표시된다. 행을 탭하면 앱이 그 Item 본문을 연다. Jetpack Glance로 구현하며 WorkManager가 1시간 간격과 수집 직후에 갱신한다.  
Avoid: shortcut, tile

