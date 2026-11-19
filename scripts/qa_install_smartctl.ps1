# Install smartmontools and capture real SMART evidence for external drives.
#
# Requires an elevated console (winget machine-scope install + raw device reads).
# Reads only: smartctl queries never start a self-test or write to a device.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\qa_install_smartctl.ps1
param(
    [string]$OutputDir = "$env:USERPROFILE\dr_smart",
    [string]$PythonExe = ''
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$repoDesktop = Join-Path $repoRoot 'desktop'
if (-not (Test-Path (Join-Path $repoDesktop 'driverepair_desktop'))) { $repoDesktop = $repoRoot }

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
try { Start-Transcript -Path (Join-Path $OutputDir '_run.log') -Append | Out-Null } catch { }

function Resolve-Python {
    if ($PythonExe -and (Test-Path $PythonExe)) { return $PythonExe }
    foreach ($candidate in @((Get-Command python.exe -ErrorAction SilentlyContinue).Source,
            "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe")) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    return $null
}

$python = Resolve-Python
Write-Host "Interpreter: $python"
if (-not $python) {
    "failed: no python interpreter" | Out-File (Join-Path $OutputDir '_complete.txt') -Encoding utf8
    exit 4
}

# 1. Install smartmontools non-interactively (exact package ID, winget verifies publisher).
& winget install --id smartmontools.smartmontools --exact --source winget `
    --accept-package-agreements --accept-source-agreements --disable-interactivity
Write-Host "winget exit: $LASTEXITCODE"

# 2. Refresh PATH for this process and locate smartctl. The installer does not
#    always publish to the Machine PATH before this process reads it, so known
#    install locations are checked explicitly.
$machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$user = [Environment]::GetEnvironmentVariable('Path', 'User')
$env:Path = "$machine;$user"
$smartctl = (Get-Command smartctl.exe -ErrorAction SilentlyContinue).Source
if (-not $smartctl) {
    foreach ($candidate in @("$env:ProgramFiles\smartmontools\bin\smartctl.exe",
            "${env:ProgramFiles(x86)}\smartmontools\bin\smartctl.exe")) {
        if (Test-Path $candidate) { $smartctl = $candidate; break }
    }
}
if ($smartctl) {
    # Make the resolved directory visible to the Python child as well.
    $env:Path = "$(Split-Path -Parent $smartctl);$env:Path"
}
Write-Host "smartctl: $smartctl"
if (-not $smartctl) {
    "failed: smartctl not found after install" | Out-File (Join-Path $OutputDir '_complete.txt') -Encoding utf8
    exit 5
}

# 3. Capture health snapshots through the application's own CLI (read-only).
Push-Location $repoDesktop
$env:PYTHONPATH = $repoDesktop
try {
    $inventory = & $python -m driverepair_desktop list --json 2>$null | Out-String
    $devices = @()
    try { $devices = ($inventory | ConvertFrom-Json | ForEach-Object { $_.id }) } catch { }

    if (-not $devices -or $devices.Count -eq 0) {
        "failed: no external disks reported" | Out-File (Join-Path $OutputDir '_complete.txt') -Encoding utf8
        exit 3
    }

    $summary = @()
    foreach ($device in $devices) {
        $name = ($device -split ':')[-1]
        $target = Join-Path $OutputDir "$name.health.json"
        & $python -m driverepair_desktop health --device $device --json *> $target
        $summary += [pscustomobject]@{ Device = $device; File = $target }
    }

    # Diagnostic: which bridge device types does smartctl actually accept here?
    # Read-only queries; the result file explains UNKNOWN health on USB docks.
    $probeLines = @()
    foreach ($device in $devices) {
        $rawPath = '\\.\' + (($device -split ':')[-1])
        foreach ($type in @('auto', 'sat', 'sat,12', 'sntjmicron', 'sntasmedia', 'sntrealtek', 'usbjmicron', 'usbjmicron,0')) {
            $arguments = @('--json', '--all')
            if ($type -ne 'auto') { $arguments += @('-d', $type) }
            $arguments += $rawPath
            $out = & $smartctl @arguments 2>&1 | Out-String
            $code = $LASTEXITCODE
            $message = (($out | Select-String -Pattern '"string"' | Select-Object -First 1).Line)
            if (-not $message) { $message = 'no message' }
            $probeLines += "$device $type exit=$code $($message.Trim())"
        }
    }
    $probeLines | Out-File (Join-Path $OutputDir 'smartctl_probe.txt') -Encoding utf8
    $probeLines | Write-Host

    $summary | Format-Table -AutoSize | Out-String | Write-Host
    "completed $(Get-Date -Format o)" | Out-File (Join-Path $OutputDir '_complete.txt') -Encoding utf8
} finally {
    Pop-Location
    try { Stop-Transcript | Out-Null } catch { }
}
