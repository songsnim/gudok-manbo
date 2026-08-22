# Feed는 30일 뒤 만료되고, Collection만 영구 보관한다

Vault의 Item을 두 폴더로 나눈다. `Resource/gudok-manbo/articles/`(Feed)의 Item은 수집일로부터 30일이 지나면 `.md` 파일째로 삭제되고, 사용자가 명시적으로 Collection으로 보낸 Item만 `Resource/gudok-manbo/collections/`에서 영구히 남는다. 수집은 하루 20여 개씩 무한히 누적되는데 읽고 나서 버릴지 남길지 결정하는 행위가 없었고, 그 결과 Vault가 "챙기지 못한 글"로 채워져 알짜를 찾을 수 없게 되기 때문이다. Feed는 받은편지함, Collection은 보관함이다.

## Considered Options

- **Collection을 frontmatter 플래그(`collected: true`)로 표시** — 파일은 `articles/`에 그대로 두고 Collection 탭은 필터링된 뷰. 거부: Feed가 계속 무한 누적되고, Obsidian에서 폴더를 열었을 때 알짜와 미처리가 섞인다.
- **만료 없이 수동 삭제만 유지** — 코드 변경 0. 거부: 현재 상태가 그것이고, 실제로 아무도 안 지운다.
- **만료 기준을 게시일(`published`)로** — 거부: 5년 전 명강의를 검색해서 담는 경로(`/search/videos`)가 있는데, 게시일 기준이면 담자마자 삭제된다. 만료의 목적은 "내가 챙길 기회를 가진 뒤 안 챙긴 글 치우기"이고, 그 시계는 수집일에서 시작한다.
- **삭제 대신 `trash/` 유예 폴더** — 거부: 결국 안 비워지는 폴더가 되어 "Vault를 가볍게 유지한다"는 목적 자체를 무너뜨린다.

## Consequences

**Feed → Collection 이동은 되돌릴 수 없다.** Collection에서 Item을 빼는 것은 완전 삭제이며, `articles/`로의 되이동은 제공하지 않는다. 되이동을 허용하면 두 달 전에 수집한 Item이 Feed로 돌아간 직후 만료로 즉시 삭제되고, 이를 피하려 frontmatter의 `date`를 갱신하면 수집일이 거짓이 된다.

**만료는 되돌릴 수 없는 파일 삭제이므로 세 겹의 안전장치를 둔다.** (1) `expire_days` 기본값은 0(만료 안 함)이며, 앱에서 30으로 바꾸는 것이 곧 기능을 켜는 행위다. (2) frontmatter `date`를 읽을 수 없는 파일은 판정 불가로 보고 삭제하지 않는다. (3) `auto_collect`를 끄면 `collect.py`가 즉시 종료하여 수집도 만료도 하지 않는다 — 스위치를 끈 상태에서 파일이 사라지는 일은 없다. 지운 파일명은 `data/collect_runs.jsonl`에 남으며, 파일이 사라진 뒤 무엇이 사라졌는지 알 수 있는 유일한 경로다.

**읽음 여부는 만료 판정에 쓰지 않는다.** 읽음 상태는 앱 로컬 Room DB에만 있어 백엔드가 알 수 없고(ADR-0002), 안 읽은 글에 예외를 주면 "안 읽은 글이 영원히 쌓임"이 그대로 돌아온다.

## Vault 경로를 `Area/`에서 `Resource/gudok-manbo/`로 옮긴 이유

폴더가 둘로 갈리는 시점에 경로도 정리했다. 이 앱의 데이터가 Vault 여러 곳에 흩어지지 않고 `Resource/gudok-manbo/` 한 폴더 아래에 모이도록 하기 위함이며, PARA 기준으로도 영구 참고자료는 Resource에 속한다. 단, 백엔드 운영 데이터(구독 목록, 앱 설정, 실행 로그)는 Vault에 두지 않고 `backend/data/`에 남긴다 — Obsidian Sync가 모바일로 끌고 갈 필요가 없는 파일이다. 경로 리터럴은 `backend/config.py`의 두 property에만 존재한다.
