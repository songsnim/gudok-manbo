---
name: ticket
description: GitHub Projects 백로그를 작업 큐로 쓰는 티켓 워크플로. 티켓 하나 = 이슈 = worktree = 브랜치 = PR. 병렬 subagent가 격리된 worktree에서 작업하고 PR까지 연다. "티켓", "backlog", "/ticket add|ready|run|sync|drop" 요청에 사용.
allowed-tools: Bash(gh:*), Bash(git:*), Bash(python:*), Read, Grep, Glob, Agent, PushNotification
---

# 티켓 워크플로

인자: `$ARGUMENTS` — 첫 단어가 서브커맨드. 없으면 `sync`.

## 불변 규칙

- **작업 단위**: 이슈 1개 = 프로젝트 카드 1개 = worktree 1개 = 브랜치 1개 = PR 1개
- **Done으로 절대 옮기지 않는다.** merge는 사람이 하고, Done은 GitHub 내장 워크플로(item closed → Done)가 처리한다. `tp.py`에 Done 옵션 ID는 없다.
- **merge하지 않는다.** `gh pr merge`는 어떤 경우에도 실행 금지.
- **상태를 세션 메모리에 두지 않는다.** 진실은 항상 GitHub(`tp.py list`, `tp.py prs`) + `git worktree list`에서 읽는다.
- **동시 실행 상한 3.** `run`의 신규 투입과 `sync`의 재투입을 합쳐서 3.

## 고정값

```
repo      songsnim/gudok-manbo
project   #2
worktree  C:/Users/User/worktrees/gudok-manbo/ticket-<n>
branch    songsnim/ticket-<n>-<slug>
helper    python .claude/skills/ticket/scripts/tp.py
```

`tp.py` 서브커맨드: `list` / `status <n> "<상태>"` / `add "<제목>" "<본문>"` / `prs`

---

## add "<제목>" [본문]

```bash
python .claude/skills/ticket/scripts/tp.py add "<제목>" "<본문>"
```

이슈 생성 + 보드 추가 + Backlog. draft item이 아니라 실제 이슈여야 한다 — PR이 `Closes #n`으로 연결해야 하므로.

## ready <n>...

```bash
python .claude/skills/ticket/scripts/tp.py status <n> "Ready"
```

Backlog는 보관함, Ready가 실행 큐다.

## run [<n>...]

번호를 주면 그 티켓만. 없으면 Ready 전부.

**1. 스펙 게이트 (subagent 투입 전, 메인 세션이 직접)**

`gh issue view <n> --repo songsnim/gudok-manbo` 로 본문을 읽고 두 가지를 확인:

- 지금 무엇이 잘못됐는가 / 무엇이 없는가
- 끝나면 어떤 상태여야 하는가

**하나라도 불명확하면 사용자에게 물어본다.** 추측해서 넘어가지 않는다. 답을 받으면 `gh issue edit <n> --body "..."`로 본문에 반영한 뒤 진행. 어디를 건드리는지는 없어도 된다 — subagent가 찾는다.

**2. worktree 준비**

```bash
git worktree add C:/Users/User/worktrees/gudok-manbo/ticket-<n> -b songsnim/ticket-<n>-<slug> main
```

이미 브랜치/worktree가 있으면 **버리지 않는다.** 그대로 재사용하고 subagent 브리프에 "이전 시도가 있다, 커밋을 확인하고 이어가라"를 넣는다.

**3. 상태 이동**

```bash
python .claude/skills/ticket/scripts/tp.py status <n> "In progress"
```

**4. subagent 투입**

`Agent` 도구, `run_in_background: true`, 티켓당 1개, 최대 3개 동시. 여러 개면 한 메시지에서 동시에 띄운다.

`isolation: "worktree"`를 **쓰지 않는다.** 그건 자체 worktree를 만들고 자동 삭제하는데, 우리는 경로와 브랜치 이름을 제어해야 하고 merge까지 유지해야 한다. 위에서 만든 경로를 브리프에 명시한다.

**5. 완료 처리**

subagent 통지가 오면:

- `ok` + `pr_url` 있으면 → `tp.py status <n> "In review"` → `PushNotification`으로 알림 (예: `#12 PR #45 열림 — 리뷰 대기`)
- `blocked`이면 → 상태 유지(In progress), 이슈에 이유가 코멘트로 남아 있음, 사용자에게 보고 + 알림

## sync

보드를 출력하되, 먼저 아래 세 가지를 처리하고 **무엇을 했는지 출력 맨 위에 명시한다.** 조용히 넘어가지 않는다.

`tp.py list`, `tp.py prs`, `git worktree list`를 읽어 대조한다.

**1. worktree 정리** — PR이 `MERGED` 또는 `CLOSED`인 티켓의 worktree를 삭제:

```bash
git worktree remove C:/Users/User/worktrees/gudok-manbo/ticket-<n> --force
```

**2. 변경 요청 재투입** — `reviewDecision`이 `CHANGES_REQUESTED`인 PR 발견 시, 확인 없이 subagent 재투입 (상한 3에 포함). 상태는 **In review 유지** — 공은 여전히 사용자에게 있다.

재투입 브리프에 추가로 넣을 것:

- `gh pr view <pr> --repo songsnim/gudok-manbo --comments` 로 리뷰 스레드를 전부 읽어라
- 각 지적마다 **고치거나, 스레드에 반론을 답글로 남겨라.** 둘 다 안 하고 넘어가는 것은 금지. 지적이 틀렸다고 판단하면 이유를 적어 반박하라 — 맹목적으로 따르지 마라
- 끝나면 push하고 `gh pr edit`/코멘트로 재리뷰를 요청하라

**3. 좀비 보고** — `In progress`인데 PR이 없고 이 세션이 띄운 subagent도 아닌 티켓은 **"확인 필요"로 출력만 한다.** 자동 재시작하지 않는다 — 실제로 돌고 있는 에이전트 위에 두 번째를 던지면 같은 worktree를 덮어쓴다. 이슈에 `blocked` 코멘트가 있으면 그 이유를 함께 보여준다.

**4. 보드 출력** — 상태별로 묶어서. 각 줄에 PR 번호와 리뷰 상태를 함께.

## drop <n>

이 일을 하지 않기로 한다. **되돌릴 수 없다 — 커밋 안 된 변경이 있으면 먼저 보여주고 확인을 받는다.**

```bash
git -C C:/Users/User/worktrees/gudok-manbo/ticket-<n> status --short   # 확인용
git worktree remove C:/Users/User/worktrees/gudok-manbo/ticket-<n> --force
git branch -D songsnim/ticket-<n>-<slug>
git push origin --delete songsnim/ticket-<n>-<slug>   # 원격에 있으면
gh pr close <pr> --repo songsnim/gudok-manbo          # PR 있으면
gh issue close <n> --repo songsnim/gudok-manbo
```

---

## Subagent 브리프

subagent에게 넘길 지시문. 티켓별로 `<...>`를 채운다.

> 너는 `songsnim/gudok-manbo`의 오픈소스 컨트리뷰터다. 이슈 #`<n>`을 처리하고 PR을 연다.
>
> **작업 위치**: `C:/Users/User/worktrees/gudok-manbo/ticket-<n>` (브랜치 `songsnim/ticket-<n>-<slug>`). **이 디렉터리 밖의 파일을 수정하지 마라.** 다른 worktree가 병렬로 돌고 있다.
>
> **티켓 본문**:
> ```
> <gh issue view <n> 출력>
> ```
>
> **절차**
> 1. `gh issue view <n> --repo songsnim/gudok-manbo`로 이슈를 다시 확인. (이전 시도가 있으면) `git log main..HEAD`로 어디까지 됐는지 확인하고 이어간다.
> 2. 코드를 고친다. 최소 변경. 요청되지 않은 리팩터링/개선 금지.
> 3. **빌드 게이트 — 통과해야 PR을 연다.**
>    - 백엔드(`backend/`) 변경: 건드린 모듈에 대해 `python -c "import ..."` 스모크. 테스트가 이미 있으면 실행.
>    - 안드로이드(`android/`) 변경: `cd android && ./gradlew assembleDebug`
>    - 실패하고 고칠 수 없으면 PR을 열지 말고 아래 `blocked` 절차로 간다.
> 4. 커밋. 메시지는 Conventional Commits (`feat:`/`fix:`/...), 저장소의 기존 커밋 스타일에 맞춘다.
> 5. `git push -u origin songsnim/ticket-<n>-<slug>`
> 6. `gh pr create --repo songsnim/gudok-manbo --base main`. 본문에 반드시 포함:
>    - **의도**: 이 티켓을 어떻게 해석했는가
>    - **변경**: 무엇을 왜 바꿨는가
>    - **검증**: 어떤 명령으로 확인했고 결과가 무엇인가
>    - `Closes #<n>`
>
> **막혔을 때 (`blocked`)**: 티켓의 전제가 틀렸거나, 사람의 결정 없이는 진행할 수 없거나, 빌드를 못 고치면 — **PR을 만들지 마라.** `gh issue comment <n> --repo songsnim/gudok-manbo --body "..."`로 막힌 지점을 구체적으로 남기고 `ok: false`로 반환한다. 잘못된 PR을 여는 것보다 멈추는 게 싸다.
>
> **금지**: `gh pr merge`, 프로젝트 상태 변경(`tp.py`), main 브랜치 조작, worktree 밖 파일 수정.
>
> **반환값**: 사람에게 하는 보고가 아니라 데이터다. 아래 JSON만 반환하라. 상세 설명은 전부 PR 본문에 쓰고 여기엔 쓰지 마라.
> ```json
> {"issue": <n>, "branch": "...", "pr_url": "..." , "ok": true, "one_line": "한 줄 요약"}
> ```
