#Requires -Version 5.1
# Removes ClefTune. Library and settings are kept unless you pass -Purge.
param([switch]$Purge)

$AppName = 'ClefTune'
$Base = Join-Path $env:LOCALAPPDATA 'ClefTune'

foreach ($dir in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
    Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $dir "$AppName.lnk")
}
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Base 'venv')
if ($Purge) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Base
    Write-Host 'Removed the app, its library, settings and cache. Downloaded music in Music\ClefTune was kept.'
} else {
    Write-Host "Removed the app. Library and settings remain in $Base (use -Purge to delete them)."
}
