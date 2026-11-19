# Read-only hardware QA sweep for Windows.
#
# Runs DriveRepair's bounded triage scan against external whole disks and writes
# one JSON result per disk. Reads only: no refresh, no capacity test, no writes.
#
# Physical-drive access requires an elevated process on Windows, so run this from
# an Administrator console (or approve the UAC prompt when launched with -Verb RunAs).
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\qa_readonly_triage.ps1
#   powershell ... -File scripts\qa_readonly_triage.ps1 -Devices windows:PhysicalDrive2,windows:PhysicalDrive3
param(
    [string[]]$Devices = @(),
    [int]$Samples = 24,
    [string]$OutputDir = "$env:USERPROFILE\dr_results"
)

$ErrorActionPreference = 'Continue'
$repoDesktop = Split-Path -Parent $PSScriptRoot

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
Push-Location $repoDesktop
$env:PYTHONPATH = '.'

try {
    if (-not $Devices -or $Devices.Count -eq 0) {
        $inventory = & python -m driverepair_desktop list --json 2>$null | Out-String
        try {
            $Devices = ($inventory | ConvertFrom-Json | ForEach-Object { $_.id })
        } catch {
            Write-Error "Could not parse drive inventory; pass -Devices explicitly."
            exit 2
        }
    }
    if (-not $Devices -or $Devices.Count -eq 0) {
        Write-Error "No external whole disks reported. Connect a drive and retry."
        exit 3
    }

    $summary = @()
    foreach ($device in $Devices) {
        $name = ($device -split ':')[-1]
        $target = Join-Path $OutputDir "$name.scan.json"
        & python -m driverepair_desktop scan --device $device --mode triage `
            --samples $Samples --ack-risk --json --no-live-dashboard *> $target
        $status = 'unknown'
        try {
            $parsed = Get-Content $target -Raw | ConvertFrom-Json
            $status = $parsed.status
        } catch {
            $status = 'unparsed-output'
        }
        $summary += [pscustomobject]@{ Device = $device; Status = $status; File = $target }
    }

    $summary | Format-Table -AutoSize
    $summary | ConvertTo-Json | Out-File (Join-Path $OutputDir '_summary.json') -Encoding utf8
    "completed $(Get-Date -Format o)" | Out-File (Join-Path $OutputDir '_complete.txt') -Encoding utf8
} finally {
    Pop-Location
}
