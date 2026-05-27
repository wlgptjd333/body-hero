# Godot 보내기 출력 폴더에 이 저장소의 tools 트리를 복사합니다(python_embed 포함).
# 사용 예:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\package_release.ps1 -ExportDir "C:\out\BodyHero"
param(
    [Parameter(Mandatory = $true)]
    [string]$ExportDir
)
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$dst = Join-Path $ExportDir "tools"
if (-not (Test-Path (Join-Path $src "udp_send_webcam_ml.py"))) {
    Write-Error "tools 폴더가 아닌 것 같습니다: $src"
}
if (Test-Path (Join-Path $src "python_embed")) {
    Write-Host "python_embed 있음 → 포함됨"
} else {
    Write-Host "python_embed 없음 — 빌드 필요 시 tools\build_python_embed.bat 실행"
}
Write-Host "Robocopy"
Write-Host "  From: $src"
Write-Host "  To:   $dst"
New-Item -ItemType Directory -Force -Path $ExportDir | Out-Null
$robolog = Join-Path $env:TEMP "body_hero_robocopy_release.log"
& robocopy.exe $src $dst /E /XD "__pycache__" ".pytest_cache" ".git" /LOG:$robolog /NFL /NDL /NJH /NJS /nc /ns /np
if ($LASTEXITCODE -ge 8) {
    Write-Error "robocopy 실패 (코드 $LASTEXITCODE). 로그: $robolog"
}
Write-Host "완료 (robocopy 종료 코드 $LASTEXITCODE, 0~7은 정상 범위)."
