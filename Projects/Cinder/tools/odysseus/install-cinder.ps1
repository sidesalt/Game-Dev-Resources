# Cinder for Odysseus: one-time setup on your Windows AI PC.
#
# Paste this line into PowerShell (Win + R, type powershell, Enter):
#   irm https://raw.githubusercontent.com/sidesalt/Game-Dev-Resources/ccr-031f1132-nxzsb1/Projects/Cinder/tools/odysseus/install-cinder.ps1 | iex
#
# It adds a small local "cinder" model that Odysseus can chat with. In Odysseus
# you then type: push, ask ..., look, undo, status, stop, help.
# It never changes Ollama, Bitez or Odysseus settings, firewall or security.

$ErrorActionPreference = "Stop"
$Branch  = "ccr-031f1132-nxzsb1"
$Repo    = "https://github.com/sidesalt/Game-Dev-Resources.git"
$Home2   = $env:USERPROFILE
$Dir     = Join-Path $Home2 "Cinder\Game-Dev-Resources"
$CfgDir  = Join-Path $Home2 ".cinder"
$Port    = 8740

function Step($text) { Write-Host "`n== $text ==" -ForegroundColor Yellow }

Step "1/5 Checking Git"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Git..."
    winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
    $env:Path += ";C:\Program Files\Git\cmd"
}

Step "2/5 Finding Python"
$Python = $null
foreach ($c in @("py", "python")) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") { $Python = $cmd.Source; break }
}
if (-not $Python) {
    # Reuse the Python that already runs Odysseus.
    $venv = Get-ChildItem -Path (Join-Path $Home2 "Documents\Codex") -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -like "*odysseus*\Scripts\python.exe" } | Select-Object -First 1
    if ($venv) { $Python = $venv.FullName }
}
if (-not $Python) {
    Write-Host "Installing Python..."
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    $Python = (Get-Command python).Source
}
Write-Host "Using $Python"

Step "3/5 Getting the Cinder project"
if (Test-Path (Join-Path $Dir ".git")) {
    git -C $Dir remote set-url origin $Repo  # follows the repo if it moved
    git -C $Dir fetch -q origin $Branch
    git -C $Dir checkout -q $Branch
    git -C $Dir pull -q --rebase --autostash origin $Branch
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path $Dir) | Out-Null
    git clone -q --branch $Branch --single-branch $Repo $Dir
}
if (-not (git -C $Dir config user.name)) { git -C $Dir config user.name "Cinder AI" }
if (-not (git -C $Dir config user.email)) { git -C $Dir config user.email "cinder-ai@users.noreply.github.com" }
Write-Host "A GitHub sign-in window may open now. Sign in so Cinder can save your changes."
git -C $Dir push --dry-run -q origin $Branch

Step "4/5 Settings (uses the AI already on this PC, Ollama on 11434)"
New-Item -ItemType Directory -Force -Path $CfgDir | Out-Null
$cfg = [ordered]@{
    repo_dir    = $Dir
    ai_url      = "http://127.0.0.1:11434"
    model       = "qwen3.5:9b"
    small_model = "qwen3.5:9b"
    think       = $false
    manage_ai   = $false
    port        = $Port
}
$cfgPath = Join-Path $CfgDir "config.json"
if (Test-Path $cfgPath) { Copy-Item $cfgPath "$cfgPath.backup-$(Get-Date -Format yyyyMMdd-HHmmss)" }
$cfg | ConvertTo-Json | Set-Content -Encoding UTF8 $cfgPath

Step "5/5 Starting Cinder now and at every login"
$Tool  = Join-Path $Dir "Projects\Cinder\tools\phone\cinder.py"
$Start = Join-Path $CfgDir "Start Cinder.cmd"
@"
@echo off
set GIT_TERMINAL_PROMPT=0
title Cinder for Odysseus
"$Python" "$Tool" serve
"@ | Set-Content -Encoding ASCII $Start
$startup = [Environment]::GetFolderPath("Startup")
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $startup "Cinder for Odysseus.lnk"))
$lnk.TargetPath = $Start
$lnk.WindowStyle = 7
$lnk.Save()
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -like "*cinder.py*serve*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Process -FilePath $Start -WindowStyle Minimized
Start-Sleep -Seconds 3
try {
    Invoke-RestMethod "http://127.0.0.1:$Port/v1/models" | Out-Null
    Write-Host "Cinder is running." -ForegroundColor Green
} catch {
    Write-Host "Cinder did not answer yet. Double-click '$Start' to start it." -ForegroundColor Red
}

Write-Host @"

LAST STEP, in Odysseus (one time):
  1. Open Odysseus settings, where your 'Bitez fleet' endpoint is listed.
  2. Add a new endpoint:
       Name:     Cinder
       URL:      http://127.0.0.1:$Port/v1
       API key:  cinder   (any text works)
  3. Start a chat and pick the model  cinder.
  4. Type  help  to see the commands, or just type  push.
"@ -ForegroundColor Cyan
