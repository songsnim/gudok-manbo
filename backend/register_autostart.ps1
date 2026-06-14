# Contents Curator — 백엔드+터널을 로그온 시 자동 실행하도록 등록한다.
#
# PC가 켜져/로그온돼 있으면 uvicorn + cloudflared quick tunnel이 자동으로 떠서
# 집 밖에서도 백엔드에 접속할 수 있다.
#
# 실행:  powershell -ExecutionPolicy Bypass -File .\register_autostart.ps1
#
# 주의: 슬립 중에는 두 프로세스도 멈춘다 → 원격 접속은 PC가 깨어 있을 때만 된다.
#       (정해진 시각의 수집 wake는 register_tasks.ps1 이 담당. 임의 시점 원격 접속까지
#        보장하려면 PC를 재우지 않도록 전원 설정에서 슬립을 끄는 편이 낫다.)

$ErrorActionPreference = "Stop"
$Script = Join-Path $PSScriptRoot "serve_remote.ps1"
$TaskName = "ContentsCurator-ServeRemote"

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Script`""

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero)   # 무제한(상시 실행)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -Description "백엔드(uvicorn) + Cloudflare quick tunnel 자동 실행" `
    -Force | Out-Null

Write-Host "등록 완료: $TaskName (로그온 시 자동 실행)"
Write-Host "지금 즉시 한 번 실행하려면: Start-ScheduledTask -TaskName $TaskName"
Write-Host "발급된 공개 주소는 data\tunnel_url.txt 에서 확인하세요."
