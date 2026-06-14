# Obsidian Vault를 Item의 SSOT로 사용

PC 백엔드가 수집·요약한 Item을 Obsidian Vault의 .md 파일로 저장하고, 이를 유일한 진실의 원천으로 삼는다. 별도 DB를 두지 않는다. Obsidian Sync가 아카이빙 경로를 무료로 처리해주고, 사용자가 이미 Vault를 운영 중이며, 개인용 단일 사용자 앱에서 DB 운영 복잡도를 감수할 이유가 없기 때문이다.

## Considered Options

- SQLite / PostgreSQL 별도 DB: 쿼리 유연성은 높지만 서버 운영 복잡도 추가
- Obsidian Vault (.md SSOT): 아카이빙·동기화를 Obsidian 생태계에 위임, 구현 단순

## Consequences

안드로이드 앱의 일상 읽기용 Feed는 Vault에서 직접 읽지 않고 PC의 FastAPI JSON 엔드포인트를 통해 읽는다. Vault는 아카이빙과 PC 측 진실의 원천 역할만 한다.
