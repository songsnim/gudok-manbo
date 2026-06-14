# Contents Curator — 수집 작업을 Windows 작업 스케줄러에 등록한다.
#
# 슬립 중인 PC를 정해진 시각에 RTC wake timer로 깨워 collect.py 를 1회 실행한다.
# (모니터는 켜지지 않는다 — 백그라운드 wake.)
#
# 반드시 "관리자 권한 PowerShell"에서 실행할 것 (powercfg 전원 설정 변경 때문).
#   PS> powershell -ExecutionPolicy Bypass -File .\register_tasks.ps1

$ErrorActionPreference = "Stop"

# ── 경로 (자동 탐지) ─────────────────────────────────────────────────────────
# 작업 디렉터리 = 이 스크립트가 있는 backend 폴더. Python = PATH에서 탐지.
$WorkDir = $PSScriptRoot
$Python  = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) { throw "python을 PATH에서 찾을 수 없습니다. Python 설치 후 다시 실행하세요." }
$Script  = "collect.py"

# 시각별 수집 개수 (한국시간 = PC 로컬시간 기준). 시각마다 별도 작업으로 등록한다.
$Schedule = @(
    @{ Hour = 6;  Count = 10 },
    @{ Hour = 11; Count = 5  },
    @{ Hour = 17; Count = 10 }
)

# ── 1. wake timer 허용 (전원 plan) ───────────────────────────────────────────
# SUB_SLEEP / "절전 모드 해제 타이머 허용" 설정 GUID = bd3b718a-... , 값 1 = 사용
$WAKE = "bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d"
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP $WAKE 1
powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP $WAKE 1
powercfg /SETACTIVE SCHEME_CURRENT
Write-Host "[1/3] wake timer 허용 완료 (AC/배터리 모두)"

# ── 2. 기존 작업 정리 ────────────────────────────────────────────────────────
# 예전 단일 작업이 남아 있으면 제거 (중복 수집 방지).
Unregister-ScheduledTask -TaskName "ContentsCurator-Collect" -Confirm:$false -ErrorAction SilentlyContinue

# ── 3. 시각별 작업 등록 ──────────────────────────────────────────────────────
# 06시 10개 / 11시 5개 / 17시 10개 (한국시간). 시각마다 별도 작업으로 wake timer 무장.
$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

foreach ($job in $Schedule) {
    $h = $job.Hour; $c = $job.Count
    $taskName = "ContentsCurator-Collect-{0:D2}00" -f $h
    $trigger  = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($h))
    $action   = New-ScheduledTaskAction -Execute $Python -Argument "$Script $c" -WorkingDirectory $WorkDir

    Register-ScheduledTask `
        -TaskName $taskName `
        -Trigger $trigger `
        -Action $action `
        -Settings $settings `
        -Description "구독 소스에서 컨텐츠 $c개 수집 (PC를 깨워 백그라운드 실행)" `
        -Force | Out-Null
    Write-Host ("[2/3] 등록: {0} — 매일 {1:D2}:00, {2}개" -f $taskName, $h, $c)
}

# ── 검증 ─────────────────────────────────────────────────────────────────────
Write-Host "[3/3] 무장된 wake timer 확인:"
powercfg /waketimers
Write-Host ""
Write-Host "완료. 테스트: 작업 스케줄러에서 'ContentsCurator-Collect-0600' 우클릭 > 실행. 로그는 data\logs\collect.log"
