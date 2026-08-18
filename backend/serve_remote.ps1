# Contents Curator — 백엔드 + Cloudflare Quick Tunnel 런처
#
# uvicorn(0.0.0.0:8000)과 cloudflared quick tunnel을 띄우고, 생성된 공개 HTTPS 주소를
# data\tunnel_url.txt 에 기록하고 화면에 출력한다. 그 주소를 폰 앱의 "서버 주소" 설정에 입력하면
# 집 밖에서도 백엔드에 접속할 수 있다.
#
# 사전 준비: cloudflared 설치
#   winget install --id Cloudflare.cloudflared
#
# 주의: quick tunnel 주소는 cloudflared를 재시작하면 바뀐다. Gist 포인터가 자동 갱신되므로
#       앱에서 다시 입력할 필요는 없다.
#
# 이 스크립트는 몇 분 간격으로 반복 실행되는 워치독을 겸한다(register_autostart.ps1 참고).
# 그래서 uvicorn/cloudflared 각각 "이미 살아 있으면 건드리지 않는다"가 되어야 한다.
# 둘은 독립 프로세스라서, uvicorn만 죽으면 터널은 살아 있고 앱은 502를 받는다.

$ErrorActionPreference = "Stop"
$WorkDir = $PSScriptRoot
$DataDir = Join-Path $WorkDir "data"
New-Item -ItemType Directory -Force $DataDir | Out-Null
$tunnelLog  = Join-Path $DataDir "tunnel.log"
$urlFile    = Join-Path $DataDir "tunnel_url.txt"
$uvicornLog = Join-Path $DataDir "uvicorn.log"

# 상위 셸/워치독이 죽어도 같이 끌려가지 않게 job 밖으로 띄운다
$shell = New-Object -ComObject WScript.Shell

# ── cloudflared 확인 ─────────────────────────────────────────────────────────
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    throw "cloudflared가 없습니다. 먼저 설치하세요:  winget install --id Cloudflare.cloudflared"
}
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) { throw "python을 PATH에서 찾을 수 없습니다." }

# ── 1. uvicorn (이미 8000 포트가 떠 있으면 건너뜀) ───────────────────────────
$listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Host "[1/2] uvicorn 이미 실행 중 (8000)"
} else {
    # WScript.Shell.Run으로 띄운다. Start-Process로 띄우면 uvicorn이 이 스크립트의 job에
    # 묶여, 워치독이나 상위 셸이 죽을 때 함께 끌려 내려간다 — 502의 실제 원인이었다.
    # cmd 리다이렉트(>>)라서 로그는 덮어쓰지 않고 이어붙는다.
    $cmd = 'cmd /c cd /d "{0}" && "{1}" -m uvicorn main:app --host 0.0.0.0 --port 8000 >> "{2}" 2>&1' `
        -f $WorkDir, $Python, $uvicornLog
    $shell.Run($cmd, 0, $false) | Out-Null
    Write-Host "[1/2] uvicorn 시작 (0.0.0.0:8000) — 로그: $uvicornLog"
    Start-Sleep -Seconds 4
    if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
        Write-Host "  경고: 8000 포트가 안 열렸다. $uvicornLog 확인:"
        Get-Content $uvicornLog -Tail 15 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" }
    }
}

# ── 2. cloudflared quick tunnel (이미 떠 있으면 그대로 둔다) ─────────────────
$url = $null
if (Get-Process cloudflared -ErrorAction SilentlyContinue) {
    Write-Host "[2/2] cloudflared 이미 실행 중 — 기존 터널 유지"
    $m = Select-String -Path $tunnelLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value }
} else {
    Remove-Item $tunnelLog -ErrorAction SilentlyContinue
    $cf = (Get-Command cloudflared).Source
    $shell.Run(('"{0}" tunnel --url http://localhost:8000 --logfile "{1}"' -f $cf, $tunnelLog), 0, $false) | Out-Null
    Write-Host "[2/2] cloudflared quick tunnel 시작 — 주소 발급 대기..."
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Path $tunnelLog) {
            $m = Select-String -Path $tunnelLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($m) { $url = $m.Matches[0].Value; break }
        }
    }
}

if ($url) {
    # 주소가 그대로면 Gist를 건드리지 않는다 — 워치독이 몇 분마다 도니까
    $prevUrl = if (Test-Path $urlFile) { (Get-Content $urlFile -Raw).Trim() } else { "" }
    if ($prevUrl -eq "$url/") {
        Write-Host "공개 주소 변동 없음: $url/"
        return
    }
    "$url/" | Out-File $urlFile -Encoding ascii -NoNewline

    # ── 고정 포인터(GitHub Gist) 자동 갱신 ───────────────────────────────────
    # .env의 GITHUB_GIST_TOKEN/GIST_ID가 있으면 새 주소를 Gist에 기록한다.
    # 폰 앱은 고정된 Gist raw 주소를 읽으므로, 주소가 바뀌어도 재입력이 필요 없다.
    $token = $null; $gistId = $null
    $envFile = Join-Path $WorkDir ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*GITHUB_GIST_TOKEN\s*=\s*(.+?)\s*$') { $token  = $Matches[1] }
            if ($line -match '^\s*GIST_ID\s*=\s*(.+?)\s*$')          { $gistId = $Matches[1] }
        }
    }
    if ($token -and $gistId) {
        try {
            $headers = @{ Authorization = "Bearer $token"; "User-Agent" = "contents-curator"; Accept = "application/vnd.github+json" }
            $body = @{ files = @{ "backend_url.txt" = @{ content = "$url/" } } } | ConvertTo-Json -Depth 5
            Invoke-RestMethod -Method Patch -Uri "https://api.github.com/gists/$gistId" -Headers $headers -Body $body | Out-Null
            Write-Host "Gist 갱신 완료 — 폰 앱이 새 주소를 자동으로 받습니다."
        } catch {
            Write-Host "Gist 갱신 실패: $($_.Exception.Message)"
        }
    } else {
        Write-Host "(.env에 GITHUB_GIST_TOKEN/GIST_ID 없음 — Gist 자동갱신 건너뜀, 수동 입력 필요)"
    }

    Write-Host ""
    Write-Host "===================================================================="
    Write-Host " 공개 주소: $url/"
    Write-Host " (Gist 자동갱신이 설정돼 있으면 앱이 알아서 이 주소를 받습니다.)"
    Write-Host " (data\tunnel_url.txt 에도 저장됨)"
    Write-Host "===================================================================="
} else {
    Write-Host "주소를 추출하지 못했습니다. data\tunnel.log 를 확인하세요."
}
