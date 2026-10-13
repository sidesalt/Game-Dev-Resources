# Cinder for Odysseus: one-time setup for a Cinder team on a Windows PC or laptop.
#
# Paste this line into PowerShell (Win + R, type powershell, Enter):
#   irm https://raw.githubusercontent.com/sidesalt/Game-Dev-Resources/ccr-031f1132-nxzsb1/Projects/Cinder/tools/odysseus/install-cinder.ps1 | iex
#
# It asks which team this machine is (A = NewBigSalt PC, B = BigOldSalt laptop,
# see Projects/Cinder/teams.json), then sets up the same thing as the phone:
# Cinder (the "cinder" model in Odysseus), Godot to test-build every monster,
# the free cloud models in Odysseus, and the team's timer. All AI runs on free
# cloud models, so this machine's GPU stays free for gaming. It never changes
# Ollama, Bitez, the firewall or security settings.

$ErrorActionPreference = "Stop"
$Branch  = "ccr-031f1132-nxzsb1"
$Repo    = "https://github.com/sidesalt/Game-Dev-Resources.git"
$Home2   = $env:USERPROFILE
$Dir     = Join-Path $Home2 "Cinder\Game-Dev-Resources"
$CfgDir  = Join-Path $Home2 ".cinder"
$Port    = 8740

function Step($text) { Write-Host "`n== $text ==" -ForegroundColor Yellow }

Step "1/7 Checking Git"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Git..."
    winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
    $env:Path += ";C:\Program Files\Git\cmd"
}

Step "2/7 Finding Python"
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

Step "3/7 Getting the Cinder project"
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

Step "4/7 Which team is this machine?"
$Team = $env:CINDER_TEAM
if (-not $Team) {
    Write-Host "  A = NewBigSalt (DigitalSalt PC): bosses and big monsters"
    Write-Host "  B = BigOldSalt (old laptop): regular enemies"
    $Team = (Read-Host "Type A or B").Trim().ToUpper()
}
if ($Team -notin @("A", "B", "C")) { $Team = "B" }
Write-Host "This machine is Team $Team."

Step "5/7 Godot (test-builds every new monster)"
$GodotDir = Join-Path $CfgDir "godot"
$Godot = Join-Path $GodotDir "Godot_v4.4.1-stable_win64_console.exe"
if (-not (Test-Path $Godot)) {
    New-Item -ItemType Directory -Force -Path $GodotDir | Out-Null
    $zip = Join-Path $GodotDir "godot.zip"
    Invoke-WebRequest -UseBasicParsing -OutFile $zip `
        "https://github.com/godotengine/godot/releases/download/4.4.1-stable/Godot_v4.4.1-stable_win64.exe.zip"
    Expand-Archive -Force $zip $GodotDir
    Remove-Item $zip
}
& $Godot --headless --path (Join-Path $Dir "Projects\Cinder") --import *> $null
Write-Host "Godot ready: $Godot"

Step "6/7 Settings and free cloud models (no local AI, the GPU stays free)"
New-Item -ItemType Directory -Force -Path $CfgDir | Out-Null
$cfgPath = Join-Path $CfgDir "config.json"
$keys = @{}
if (Test-Path $cfgPath) {
    Copy-Item $cfgPath "$cfgPath.backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
    $old = Get-Content $cfgPath -Raw | ConvertFrom-Json
    if ($old.keys) { $old.keys.PSObject.Properties | ForEach-Object { $keys[$_.Name] = $_.Value } }
}
if (-not $keys["OLLAMA_API_KEY"]) {
    $k = (Read-Host "Ollama Cloud API key from ollama.com/settings/keys (Enter to skip)").Trim()
    if ($k) { $keys["OLLAMA_API_KEY"] = $k }
}
$cfg = [ordered]@{
    repo_dir   = $Dir
    team       = $Team
    cloud_only = $true
    manage_ai  = $false
    godot      = $Godot
    port       = $Port
    keys       = $keys
}
$cfg | ConvertTo-Json | Set-Content -Encoding UTF8 $cfgPath

# Odysseus: add the free models (OVHcloud, Ollama Cloud) and Cinder, using Odysseus's own Python.
$OdyPy = Get-ChildItem -Path $Home2 -Recurse -Depth 6 -Filter python.exe -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "odysseus[^\\]*\\venv\\Scripts\\python.exe$" } | Select-Object -First 1
if ($OdyPy) {
    $OdyDir = Split-Path (Split-Path (Split-Path $OdyPy.FullName))
    $Helper = Join-Path $Dir "Projects\Cinder\tools\odysseus\add_free_endpoints.py"
    Push-Location $OdyDir
    if ($keys["OLLAMA_API_KEY"]) { & $OdyPy.FullName $Helper --ollama-key $keys["OLLAMA_API_KEY"] }
    else { & $OdyPy.FullName $Helper }
    Pop-Location
    Write-Host "Restart Odysseus once to see the free models." -ForegroundColor Yellow
} else {
    Write-Host "Odysseus was not found under $Home2. Add the endpoints by hand (see ODYSSEUS.md)." -ForegroundColor Yellow
}

Step "7/7 Starting Cinder and the team timer, now and at every login"
$Tool  = Join-Path $Dir "Projects\Cinder\tools\phone\cinder.py"
$Start = Join-Path $CfgDir "Start Cinder.cmd"
$TeamCmd = Join-Path $CfgDir "Cinder Team.cmd"
@"
@echo off
set GIT_TERMINAL_PROMPT=0
title Cinder Team $Team (works by itself every few hours)
:loop
"$Python" "$Tool" auto
timeout /t 60 /nobreak >nul
goto loop
"@ | Set-Content -Encoding ASCII $TeamCmd
@"
@echo off
set GIT_TERMINAL_PROMPT=0
title Cinder for Odysseus
start "" /min "$TeamCmd"
:serve
"$Python" "$Tool" serve
timeout /t 5 /nobreak >nul
goto serve
"@ | Set-Content -Encoding ASCII $Start
$startup = [Environment]::GetFolderPath("Startup")
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $startup "Cinder for Odysseus.lnk"))
$lnk.TargetPath = $Start
$lnk.WindowStyle = 7
$lnk.Save()
# Stop an older Cinder (and its loop windows) so running setup again never doubles the team.
Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -like "python*" -and $_.CommandLine -like "*cinder.py*") -or
    ($_.Name -eq "cmd.exe" -and ($_.CommandLine -like "*Start Cinder.cmd*" -or $_.CommandLine -like "*Cinder Team.cmd*"))
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Process -FilePath $Start -WindowStyle Minimized
Start-Sleep -Seconds 3
try {
    Invoke-RestMethod "http://127.0.0.1:$Port/v1/models" | Out-Null
    Write-Host "Cinder is running as Team $Team." -ForegroundColor Green
} catch {
    Write-Host "Cinder did not answer yet. Double-click '$Start' to start it." -ForegroundColor Red
}

Write-Host @"

Done. Team $Team now works by itself every few hours (see teams.json).
In Odysseus, pick the model  cinder  and type  team  to see its job, or  make a lava golem.
"@ -ForegroundColor Cyan
