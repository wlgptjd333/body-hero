param()

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Version = "3.10.11"
$ToolsDir = Join-Path $PSScriptRoot ".." -Resolve | Join-Path -ChildPath "tools"
$EmbedDir = Join-Path $ToolsDir "python_embed"
$ZipOut  = Join-Path $ToolsDir "python_ml_env.zip"
$TempZip = Join-Path $env:TEMP "python-embed.zip"

Write-Host "[1/6] Cleaning existing python_embed..."
if (Test-Path $EmbedDir) { Remove-Item -Recurse -Force $EmbedDir }
New-Item -ItemType Directory -Force -Path $EmbedDir | Out-Null

Write-Host "[2/6] Downloading Embedded Python $Version ..."
$EmbedUrl = "https://www.python.org/ftp/python/$Version/python-$Version-embed-amd64.zip"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
(New-Object Net.WebClient).DownloadFile($EmbedUrl, $TempZip)
if (-not (Test-Path $TempZip)) {
    Write-Error "Download failed"
    exit 1
}

Write-Host "[3/6] Extracting..."
Expand-Archive -Path $TempZip -DestinationPath $EmbedDir -Force
Remove-Item -Force $TempZip

Write-Host "[4/6] Enabling site-packages + tools directory..."
$PthFiles = Get-ChildItem -Path $EmbedDir -Filter "*._pth" | Select-Object -First 1
if ($PthFiles) {
    $PthPath = $PthFiles.FullName
    # Add tools dir (..) so scripts can import local modules (cv_capture, pose_normalize, etc.)
    $Content = @"
python310.zip
.
..

import site
"@
    Set-Content -Path $PthPath -Value $Content -NoNewline
    Write-Host "  $PthPath modified (site enabled + .. added)"
} else {
    Write-Warning "No .pth file found"
}

Write-Host "[5/6] Installing pip + packages (may take 10-20 minutes)..."
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$GetPip = Join-Path $env:TEMP "get-pip.py"
(New-Object Net.WebClient).DownloadFile($GetPipUrl, $GetPip)
$PythonExe = Join-Path $EmbedDir "python.exe"

& $PythonExe $GetPip --no-warn-script-location
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install failed"
    exit 1
}

$ReqFile = Join-Path $ToolsDir "requirements_ml.txt"
& $PythonExe -m pip install -r $ReqFile --no-warn-script-location
if ($LASTEXITCODE -ne 0) {
    Write-Error "Package install failed. Check $ReqFile"
    exit 1
}

Write-Host "[5b/6] Adding UTF-8 sitecustomize.py..."
$SiteCustomize = Join-Path $EmbedDir "Lib\site-packages\sitecustomize.py"
@"
import sys
if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
"@ | Set-Content -Path $SiteCustomize -Encoding UTF8
Write-Host "  $SiteCustomize created"

Write-Host "[6/6] Packaging python_ml_env.zip..."
if (Test-Path $ZipOut) { Remove-Item -Force $ZipOut }
# Use embedded Python's zipfile module (Compress-Archive drops root files like ._pth)
& $PythonExe -c @"
import zipfile, os
src = r'$EmbedDir'
dst = r'$ZipOut'
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for root, dirs, files in os.walk(src):
        for f in files:
            path = os.path.join(root, f)
            arc = os.path.relpath(path, src)
            z.write(path, arc)
"@

Write-Host ""
Write-Host "============================================================"
Write-Host "Build complete!"
Write-Host ""
Write-Host "Created: tools\python_ml_env.zip"
Write-Host ""
Write-Host "Upload to GitHub Releases:"
Write-Host "  gh release create v1.0.0 --title \"v1.0.0\" --notes \"Initial release\""
Write-Host "  gh release upload v1.0.0 tools\python_ml_env.zip"
Write-Host ""
