# Elevated Adaptive Refresh with a REAL console CLI dashboard.
#
# Why prior launches looked "stuck" after "Launching...":
# 1) Piping Python with `2>&1` under `$ErrorActionPreference = Stop` turns
#    dashboard stderr lines into terminating ErrorRecords — script dies instantly.
# 2) Naming a splat array `$args` collides with PowerShell's automatic variable.
# 3) Redirecting/piping makes stderr non-TTY so the panel never paints live.
#
# This script must be started elevated. It keeps Python on the console (no pipe).
param(
    [Parameter(Mandatory=$true)][string]$Device,
    [Parameter(Mandatory=$true)][string]$ConfirmIdentity,
    [int]$Samples = 96,
    [string]$Mode = "adaptive",
    [string]$JournalBackend = "disk",
    [string]$AfterRun = "keep"
)

$ErrorActionPreference = "Continue"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Desktop = Join-Path $Root "desktop"
$Temp = Join-Path $Root ".agent-temp"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Log = Join-Path $Temp "live_adaptive_cliui_$Stamp.log"
$Journal = Join-Path $Temp "refresh_secure_adaptive_$Stamp"

New-Item -ItemType Directory -Path $Temp -Force | Out-Null
function Log([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format o), $Message
    Add-Content -Path $Log -Value $line -ErrorAction SilentlyContinue
    Write-Host $line
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
Log ("Admin=" + $isAdmin)
if (-not $isAdmin) {
    Write-Host "ERROR: Run elevated (Administrator)." -ForegroundColor Red
    exit 2
}

if ($JournalBackend -ne "disk") {
    throw "Physical media refresh requires a durable disk journal."
}
if ($Device -notmatch '^windows:PhysicalDrive[0-9]+$') {
    throw "Select an explicit windows:PhysicalDriveN from 'driverepair list'."
}
$Confirm = Read-Host "DANGEROUS: Type the full device ID '$Device' to confirm physical writes"
if ($Confirm -cne $Device) {
    throw "Device ID did not match; no writes initiated."
}
Set-Location $Desktop
$env:PYTHONPATH = $Desktop
$env:PYTHONUNBUFFERED = "1"
$env:DRIVEREPAIR_FORCE_TTY_DASHBOARD = "1"
$env:DRIVEREPAIR_COLOR = "1"

Log ("Launching Adaptive Refresh CLI UI device=$Device samples=$Samples")
Log ("journal=$Journal")
Log ("transcript=$Log")
Write-Host ""
Write-Host "Live dashboard draws below. Do not close this window until finished." -ForegroundColor Cyan
Write-Host ""

try { Stop-Transcript | Out-Null } catch {}
Start-Transcript -Path $Log -Append | Out-Null

if (-not $ConfirmIdentity -or $ConfirmIdentity.Length -ne 12) {
    throw "Pass -ConfirmIdentity with the current 12-character identity_hint from list --json."
}

$pyArgs = @(
    "-3", "-u", "-m", "driverepair_desktop", "refresh-external",
    "--device", $Device,
    "--journal", $Journal,
    "--mode", $Mode,
    "--journal-backend", $JournalBackend,
    "--adaptive-samples", "$Samples",
    "--chunk-mib", "1",
    "--slow-multiplier", "2.0",
    "--consistency-reads", "2",
    "--after-run", $AfterRun,
    "--live-dashboard",
    "--confirm-identity", $ConfirmIdentity,
    "--ack-risk", "--ack-destructive", "--ack-no-backup", "--ack-data-loss-risk",
    "--ack-usb-bridge-risk", "--ack-unvalidated-hardware"
)

# Direct console invoke — NOT piped, NOT redirected.
& py @pyArgs
$code = $LASTEXITCODE
Log ("elevated_exit=" + $code)
try { Stop-Transcript | Out-Null } catch {}
exit $code
