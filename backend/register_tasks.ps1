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
$TaskName = "ContentsCurator-Collect"

# ── 1. wake timer 허용 (전원 plan) ───────────────────────────────────────────
# SUB_SLEEP / "절전 모드 해제 타이머 허용" 설정 GUID = bd3b718a-... , 값 1 = 사용
$WAKE = "bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d"
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP $WAKE 1
powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP $WAKE 1
powercfg /SETACTIVE SCHEME_CURRENT
Write-Host "[1/3] wake timer 허용 완료 (AC/배터리 모두)"

# ── 2. 트리거 구성 (SPEC 시간대) ─────────────────────────────────────────────
# 새벽 03·04·05·06시 매일 + 평일 10·11·12·13·14시.
# 시각마다 별도 트리거를 두어 각자 wake timer를 무장시킨다 (반복 옵션보다 안정적).
$weekdays = "Monday","Tuesday","Wednesday","Thursday","Friday"
$triggers = @()
foreach ($h in 3,4,5,6) {
    $triggers += New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($h))
}
foreach ($h in 10,11,12,13,14) {
    $triggers += New-ScheduledTaskTrigger -Weekly -DaysOfWeek $weekdays -At ([datetime]::Today.AddHours($h))
}

# ── 3. 작업 등록 ─────────────────────────────────────────────────────────────
$action = New-ScheduledTaskAction -Execute $Python -Argument $Script -WorkingDirectory $WorkDir

$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

# 로그온한 현재 사용자로 실행 (슬립은 세션을 유지하므로 wake 후 정상 실행됨)
Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $triggers `
    -Action $action `
    -Settings $settings `
    -Description "구독 소스에서 컨텐츠 수집 (PC를 깨워 백그라운드 실행)" `
    -Force | Out-Null
Write-Host "[2/3] 작업 등록 완료: $TaskName (트리거 $($triggers.Count)개)"

# ── 검증 ─────────────────────────────────────────────────────────────────────
Write-Host "[3/3] 무장된 wake timer 확인:"
powercfg /waketimers
Write-Host ""
Write-Host "완료. 테스트: 작업 스케줄러에서 '$TaskName' 우클릭 > 실행. 로그는 data\logs\collect.log"
