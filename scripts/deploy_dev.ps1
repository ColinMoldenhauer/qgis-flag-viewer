# Symlinks flag_viewer/ into the active QGIS profile's plugins folder so
# QGIS picks up edits immediately (restart QGIS, or use Plugin Reloader,
# after each change). Run from a PowerShell prompt with permission to
# create symlinks (Developer Mode enabled, or run as Administrator).
#
# Usage: pwsh -File scripts/deploy_dev.ps1 [-Profile default]

param(
    [string]$Profile = "default"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $RepoRoot "flag_viewer"
$PluginsDir = Join-Path $env:APPDATA "QGIS\QGIS3\profiles\$Profile\python\plugins"
$Target = Join-Path $PluginsDir "flag_viewer"

if (-not (Test-Path $PluginsDir)) {
    New-Item -ItemType Directory -Force -Path $PluginsDir | Out-Null
}

if (Test-Path $Target) {
    Write-Host "Target already exists, removing: $Target"
    Remove-Item -Recurse -Force $Target
}

New-Item -ItemType SymbolicLink -Path $Target -Target $Source | Out-Null
Write-Host "Linked $Source -> $Target"
Write-Host "Enable 'Flag Viewer' in QGIS: Plugins > Manage and Install Plugins."
