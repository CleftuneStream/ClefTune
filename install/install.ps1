#Requires -Version 5.1
<#
  ClefTune installer for Windows 10/11 (per-user, no admin rights needed).
    .\install\install.ps1            interactive
    .\install\install.ps1 -Yes       don't ask questions
  Or double-click install\install.bat
#>
param([switch]$Yes, [switch]$NoDesktopShortcut)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$AppName = 'ClefTune'
$Src = Split-Path -Parent $PSScriptRoot
$Base = Join-Path $env:LOCALAPPDATA 'ClefTune'
$Venv = Join-Path $Base 'venv'

function Say($m)  { Write-Host "==> $m" -ForegroundColor Magenta }
function Ok($m)   { Write-Host " ok $m" -ForegroundColor Green }
function Warn($m) { Write-Host " !! $m" -ForegroundColor Yellow }
function Ask($q)  { if ($Yes) { return $true }; return ((Read-Host "$q [Y/n]") -notmatch '^[nN]') }
function Have($c) { return [bool](Get-Command $c -ErrorAction SilentlyContinue) }

function Find-Python {
    # pywebview's Windows backend needs pythonnet, which ships wheels for these versions first
    foreach ($v in '3.13', '3.12', '3.11', '3.10', '3.14') {
        if (Have 'py') {
            $exe = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
        }
        $direct = Join-Path $env:LOCALAPPDATA ("Programs\Python\Python" + $v.Replace('.', '') + "\python.exe")
        if (Test-Path $direct) { return $direct }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike '*WindowsApps*') {   # skip the Microsoft Store alias stub
        $ver = & $cmd.Source -c "import sys; print('%d.%d' % sys.version_info[:2])"
        if ([version]$ver -ge [version]'3.10') { return $cmd.Source }
    }
    return $null
}

# ---------------------------------------------------------------- Python
$py = Find-Python
if (-not $py) {
    Warn 'Python 3.10+ was not found.'
    if ((Have 'winget') -and (Ask 'Install Python 3.12 with winget now?')) {
        winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
        $py = Find-Python
    }
    if (-not $py) { throw 'Install Python 3.12 from https://www.python.org/downloads/ (tick "Add python.exe to PATH"), then run this installer again.' }
}
Ok "Python: $py"

# ---------------------------------------------------------------- WebView2 (native window)
$wv2 = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
$hasWebView2 = (Test-Path "HKLM:\SOFTWARE\WOW6432Node\$wv2") -or (Test-Path "HKLM:\SOFTWARE\$wv2") -or (Test-Path "HKCU:\SOFTWARE\$wv2")
if ($hasWebView2) { Ok 'WebView2 runtime found' }
elseif ((Have 'winget') -and (Ask 'Microsoft Edge WebView2 runtime is missing (needed for the app window). Install it?')) {
    winget install -e --id Microsoft.EdgeWebView2Runtime --accept-package-agreements --accept-source-agreements
} else { Warn 'No WebView2: the app will open in your web browser instead of its own window.' }

# ---------------------------------------------------------------- app
Say "Creating virtual environment in $Venv"
New-Item -ItemType Directory -Force -Path $Base | Out-Null
& $py -m venv --clear $Venv
if ($LASTEXITCODE -ne 0) { throw 'Creating the virtual environment failed.' }
$vpy = Join-Path $Venv 'Scripts\python.exe'
& $vpy -m pip install --quiet --upgrade pip wheel

$target = $Src
if ((Have 'deno') -or (Have 'node') -or (Have 'bun')) { Ok 'JavaScript runtime found; not bundling Deno' }
else { Say 'No Deno/Node/Bun found: bundling Deno for yt-dlp (~90 MB)'; $target = "$Src[deno]" }

Say "Installing $AppName and its Python dependencies (this can take a minute)"
& $vpy -m pip install --quiet --upgrade "$target"
if ($LASTEXITCODE -ne 0) { throw 'pip install failed (see the messages above).' }

# ---------------------------------------------------------------- optional ffmpeg
if (Have 'ffmpeg') { Ok 'ffmpeg found: downloads get tags and cover art' }
elseif ((Have 'winget') -and (Ask 'Install ffmpeg (optional, adds tags and cover art to downloads)?')) {
    winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
}

# ---------------------------------------------------------------- shortcuts
$launcher = Join-Path $Venv 'Scripts\cleftune-gui.exe'
$launchArgs = ''
if (-not (Test-Path $launcher)) { $launcher = Join-Path $Venv 'Scripts\pythonw.exe'; $launchArgs = '-m cleftune' }
$iconPath = & $vpy -c "import cleftune, os; print(os.path.join(os.path.dirname(cleftune.__file__), 'web', 'icon.ico'))"
$shell = New-Object -ComObject WScript.Shell
$targets = @([Environment]::GetFolderPath('Programs'))
if (-not $NoDesktopShortcut) { $targets += [Environment]::GetFolderPath('Desktop') }
foreach ($dir in $targets) {
    $lnk = $shell.CreateShortcut((Join-Path $dir "$AppName.lnk"))
    $lnk.TargetPath = $launcher
    $lnk.Arguments = $launchArgs
    $lnk.WorkingDirectory = $Base
    $lnk.IconLocation = $iconPath.Trim()
    $lnk.Description = 'Unofficial YouTube Music client'
    $lnk.Save()
}
Ok 'Start menu and desktop shortcuts created'

Write-Host ''
Ok "$AppName installed. Start it from the Start menu or the desktop shortcut."
