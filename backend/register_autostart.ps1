# Contents Curator — 백엔드+터널 워치독을 로그온 시 자동 실행하도록 등록한다.
#
# PC가 켜져/로그온돼 있으면 uvicorn + cloudflared quick tunnel이 자동으로 뜨고,
# 둘 중 하나가 죽으면 워치독이 5분 안에 되살린다. 집 밖에서도 백엔드에 접속할 수 있다.
#
# 실행:  powershell -ExecutionPolicy Bypass -File .\register_autostart.ps1
#
# 작업 스케줄러(Register-ScheduledTask)를 안 쓴다 — 관리자 권한을 요구한다.
# Startup 폴더의 vbs는 권한 없이 창도 안 띄우고 실행된다.
#
# 주의: 슬립 중에는 두 프로세스도 멈춘다 → 원격 접속은 PC가 깨어 있을 때만 된다.
#       (정해진 시각의 수집 wake는 register_tasks.ps1 이 담당. 임의 시점 원격 접속까지
#        보장하려면 PC를 재우지 않도록 전원 설정에서 슬립을 끄는 편이 낫다.)

$ErrorActionPreference = "Stop"
$Serve = Join-Path $PSScriptRoot "serve_remote.ps1"
$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$Vbs = Join-Path $StartupDir "ContentsCurator-ServeRemote.vbs"

# 루프를 vbs 안에 둔다. PowerShell 루프 프로세스는 자신을 띄운 셸이 사라질 때 함께
# 끌려 내려갔다. Explorer가 로그온 때 띄우는 wscript.exe는 이 PC에서 며칠씩 살아 있다.
# Run의 3번째 인자 True = 완료까지 대기 → 실행이 겹치지 않는다.
# vbs는 cscript 기본 인코딩으로 읽히므로 주석까지 ASCII로 쓴다 — 한글은 깨진다
$content = @"
' Contents Curator - backend + cloudflare tunnel watchdog.
' Runs serve_remote.ps1 at logon and every 5 minutes. That script leaves whichever
' process is already alive untouched, so only the dead one comes back.
' Why the loop: uvicorn and cloudflared are independent. If only uvicorn dies the
' tunnel keeps answering and the app gets 502 forever.
' No admin rights needed (Register-ScheduledTask requires elevation), no console window.
Dim sh
Set sh = CreateObject("WScript.Shell")
Do
  sh.Run "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""$Serve""", 0, True
  WScript.Sleep 300000
Loop
"@

Set-Content -Path $Vbs -Value $content -Encoding ascii
Write-Host "등록 완료: $Vbs (로그온 시 워치독 실행)"

# 기존 작업 스케줄러 항목이 남아 있으면 중복 실행된다
$task = Get-ScheduledTask -TaskName "ContentsCurator-ServeRemote" -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "경고: 작업 스케줄러에 ContentsCurator-ServeRemote가 남아 있다. 중복 실행을 막으려면"
    Write-Host "      관리자 PowerShell에서: Unregister-ScheduledTask -TaskName ContentsCurator-ServeRemote -Confirm:`$false"
}

Write-Host ""
Write-Host "지금 즉시 워치독을 띄우려면:"
Write-Host "  wscript.exe `"$Vbs`""
Write-Host ""
Write-Host "로그:"
Write-Host "  data\uvicorn.log     — uvicorn 출력 (죽은 이유가 여기 남는다)"
Write-Host "  data\tunnel.log      — cloudflared 출력"
Write-Host "  data\tunnel_url.txt  — 발급된 공개 주소"
