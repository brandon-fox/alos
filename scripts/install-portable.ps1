<#
.SYNOPSIS
    Builds and installs ALOS into a self-contained portable runtime directory (or uv tool),
    initializes ALOS_HOME, runs preflight doctor checks, and optionally registers a user
    Windows Scheduled Task to run the preemptible compute daemon on logon.
#>
param(
    [string]$Prefix = (Join-Path $HOME ".alos\runtime"),
    [string]$AlosHome = (Join-Path $HOME ".alos"),
    [switch]$UseUvTool,
    [switch]$RegisterStartupTask,
    [switch]$UnregisterStartupTask
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$TaskName = "ALOS-Preemptible-Governor"

if ($UnregisterStartupTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task '$TaskName' (if present)." -ForegroundColor Green
    exit 0
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "'uv' is required to build and install the portable ALOS wheel."
}

Set-Location $RepoRoot
Write-Host "[1/4] Building portable ALOS wheel..." -ForegroundColor Cyan
$DistDir = Join-Path $Prefix "wheels"
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
uv build --wheel --out-dir $DistDir
$Wheel = Get-ChildItem -Path $DistDir -Filter "alos-*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $Wheel) {
    throw "Wheel build failed: no alos-*.whl artifact found in $DistDir"
}

if ($UseUvTool) {
    Write-Host "[2/4] Installing ALOS CLI tools via 'uv tool install'..." -ForegroundColor Cyan
    uv tool install --force $Wheel.FullName
    $AlosExe = "alos"
} else {
    $VenvDir = Join-Path $Prefix "venv"
    Write-Host "[2/4] Creating relocatable runtime environment at $VenvDir..." -ForegroundColor Cyan
    uv venv $VenvDir --python 3.12 --allow-existing
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    uv pip install --python $VenvPython --upgrade $Wheel.FullName
    $AlosExe = Join-Path $VenvDir "Scripts\alos.exe"
}

Write-Host "[3/4] Bootstrapping ALOS_HOME at $AlosHome..." -ForegroundColor Cyan
& $AlosExe --home $AlosHome bootstrap

Write-Host "[4/4] Running production readiness doctor..." -ForegroundColor Cyan
& $AlosExe --home $AlosHome doctor --json

if ($RegisterStartupTask) {
    Write-Host "Registering user logon Scheduled Task '$TaskName'..." -ForegroundColor Cyan
    $Action = New-ScheduledTaskAction -Execute $AlosExe -Argument "--home `"$AlosHome`" daemon --poll-s 2.0"
    $Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
    Write-Host "Registered '$TaskName' to start automatically at logon." -ForegroundColor Green
}

Write-Host "`nPortable ALOS installation complete! Binary: $AlosExe" -ForegroundColor Green
