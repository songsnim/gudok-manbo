# 아카이빙 경로와 일상 읽기 경로를 분리

콘텐츠 전달 경로를 두 개로 분리한다. (1) Vault → Obsidian Sync → 모바일 Obsidian 앱 (아카이빙·검색용), (2) Vault → FastAPI → Tailscale → 안드로이드 커스텀 앱·위젯 (매일 읽기용). Android Scoped Storage 정책상 Obsidian Sync가 내려주는 파일을 외부 앱이 읽을 수 없어, 단일 경로로는 커스텀 앱과 위젯을 구현할 수 없기 때문이다.

## Consequences

읽음 상태 등 일상 읽기 상태는 휘발성으로 앱 로컬 Room DB에만 저장된다. Vault는 SSOT이지만 읽음 여부는 추적하지 않는다.
