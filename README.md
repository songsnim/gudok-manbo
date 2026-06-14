# Contents Curator

개인용 콘텐츠 큐레이션 앱. 빅테크 추천 알고리즘을 벗어나, 직접 선택한 소스와 AI 에이전트가 자율 탐색한 소스에서만 콘텐츠를 수집·요약해 매일 읽는다.

- **백엔드 (Python / FastAPI)**: 집 PC에서 구독 소스를 수집·요약해 Obsidian Vault(`.md`)에 저장하고 JSON API로 서빙. Windows 작업 스케줄러가 PC를 깨워 백그라운드 수집.
- **안드로이드 앱 (Kotlin / Compose)**: 같은 Wi-Fi에서 백엔드에 접속해 오늘의 피드를 읽고, 구독 관리·AI 탐색·홈 위젯 제공.

자세한 설계는 [`docs/SPEC.md`](docs/SPEC.md), [`docs/adr/`](docs/adr/), [`CONTEXT.md`](CONTEXT.md) 참고.

---

## 백엔드 실행

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # 값 채우기 (VAULT_PATH, OPENROUTER_API_KEY 등)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- 같은 Wi-Fi의 폰이 접속하려면 `--host 0.0.0.0` 필수, Windows 방화벽에서 8000 포트 인바운드 허용.
- 자동 수집 스케줄 등록(관리자 PowerShell): `backend/register_tasks.ps1` — PC를 정해진 시각에 깨워 수집.
- 런타임 데이터(`.env`, `data/*.json`, `data/*.db`, 세션 쿠키)는 커밋되지 않는다(`.gitignore`).

## 앱 빌드 / 배포

릴리스 APK는 **GitHub Actions가 `main` push 시 자동 빌드·서명**해 GitHub Release에 첨부한다(`.github/workflows/release.yml`). 버전 코드는 빌드 번호로 자동 증가한다.

### 폰 설치 — Obtainium (자동 업데이트)

[Obtainium](https://github.com/ImranR98/Obtainium)을 쓰면 새 릴리스를 자동 감지해 업데이트한다.

1. 폰에 Obtainium 설치.
2. **Add App** → 이 레포 URL 입력 → release APK 자동 감지.
3. 설치(첫 회 "알 수 없는 출처 설치" 허용). 이후 새 릴리스가 올라오면 Obtainium이 업데이트 알림.

> ⚠️ 기존에 **debug 빌드**(Android Studio/`adb`로 설치한 것)가 폰에 있으면 서명이 달라 업데이트가 막힌다. 첫 release 설치 전 **기존 앱을 제거**할 것.

### 로컬 빌드

설정은 환경변수 → `android/local.properties`(gitignore됨) 순으로 읽는다. 로컬 빌드 시 `local.properties`에:

```properties
API_BASE_URL=http://<PC의 LAN IP>:8000/
# release 서명 빌드 시에만:
KEYSTORE_PATH=../../keystore/release.jks
KEYSTORE_PASSWORD=...
KEY_ALIAS=curator
KEY_PASSWORD=...
```

```bash
cd android
./gradlew assembleDebug      # 또는 assembleRelease (서명)
```

## CI에 필요한 GitHub Secrets

레포 **Settings → Secrets and variables → Actions** 에 등록:

| Secret | 설명 |
|---|---|
| `KEYSTORE_BASE64` | release 키스토어(`.jks`)를 base64 인코딩한 값 |
| `KEYSTORE_PASSWORD` | 키스토어 비밀번호 |
| `KEY_ALIAS` | 키 별칭 (예: `curator`) |
| `KEY_PASSWORD` | 키 비밀번호 |
| `API_BASE_URL` | 앱이 접속할 백엔드 주소 (예: `http://192.168.x.x:8000/`) |

> 키스토어와 비밀번호는 절대 커밋하지 말 것. 키를 잃어버리면 같은 앱으로 업데이트할 수 없으니 안전하게 보관한다.
