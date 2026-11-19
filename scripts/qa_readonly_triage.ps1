# Read-only hardware QA sweep for Windows.
#
# Runs DriveRepair's bounded triage scan against external whole disks and writes
# one JSON result per disk plus a transcript. Reads only: no refresh, no capacity
# test, no writes.
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
    [string]$OutputDir = "$env:USERPROFILE\dr_results",
    [string]$PythonExe = ''
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$repoDesktop = Join-Path $repoRoot 'desktop'
if (-not (Test-Path (Join-Path $repoDesktop 'driverepair_desktop'))) {
    $repoDesktop = $repoRoot
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$logPath = Join-Path $OutputDir '_run.log'
try { Start-Transcript -Path $logPath -Append | Out-Null } catch { }

function Resolve-Python {
    if ($PythonExe -and (Test-Path $PythonExe)) { return $PythonExe }
    foreach ($candidate in @(
            (Get-Command python.exe -ErrorAction SilentlyContinue).Source,
            "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
            'C:\Python311\python.exe')) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    return $null
}

$interpreter = Resolve-Python
Write-Host "Interpreter: $interpreter"
if (-not $interpreter) {
    "failed: no python interpreter found" | Out-File (Join-Path $OutputDir '_complete.txt') -Encoding utf8
    try { Stop-Transcript | Out-Null } catch { }
    exit 4
}

Push-Location $repoDesktop
$env:PYTHONPATH = $repoDesktop
Write-Host "Working directory: $repoDesktop"

try {
    if (-not $Devices -or $Devices.Count -eq 0) {
        $inventory = & $interpreter -m driverepair_desktop list --json 2>$null | Out-String
        Write-Host "Inventory length: $($inventory.Length)"
        try {
            $Devices = ($inventory | ConvertFrom-Json | ForEach-Object { $_.id })
        } catch {
            Write-Host "Inventory parse failed: $_"
            $Devices = @()
        }
    }
    if (-not $Devices -or $Devices.Count -eq 0) {
        "failed: no external whole disks reported" | Out-File (Join-Path $OutputDir '_complete.txt') -Encoding utf8
        exit 3
    }

    $summary = @()
    foreach ($device in $Devices) {
        $name = ($device -split ':')[-1]
        $target = Join-Path $OutputDir "$name.scan.json"
        Write-Host "Scanning $device -> $target"
        & $interpreter -m driverepair_desktop scan --device $device --mode triage `
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

    $summary | Format-Table -AutoSize | Out-String | Write-Host
    $summary | ConvertTo-Json | Out-File (Join-Path $OutputDir '_summary.json') -Encoding utf8
    "completed $(Get-Date -Format o)" | Out-File (Join-Path $OutputDir '_complete.txt') -Encoding utf8
} catch {
    "failed: $_" | Out-File (Join-Path $OutputDir '_complete.txt') -Encoding utf8
    Write-Host "ERROR: $_"
} finally {
    Pop-Location
    try { Stop-Transcript | Out-Null } catch { }
}
