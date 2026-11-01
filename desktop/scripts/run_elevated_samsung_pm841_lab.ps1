# Non-interactive elevated lab for Samsung PM841 on USB = Drive E / PhysicalDrive2.
# Outputs NEVER go to E:. Journal/metrics/images on D:.
# Launch: Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-File',<this>
param(
    [string]$Device = "windows:PhysicalDrive2",
    [string]$IdentityHint = "e5a0dfacc956",
    [string]$LabRoot = "D:\DriveRepairLab\samsung_pm841_256_20261101"
)

$ErrorActionPreference = "Continue"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Desktop = Join-Path $Root "desktop"
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "Administrator required for PhysicalDrive access." }

New-Item -ItemType Directory -Force -Path $LabRoot,
    (Join-Path $LabRoot "metrics"),
    (Join-Path $LabRoot "journal"),
    (Join-Path $LabRoot "monitor"),
    (Join-Path $LabRoot "images"),
    (Join-Path $LabRoot "recovery") | Out-Null

Set-Location $Desktop
$env:PYTHONPATH = $Desktop
$env:PYTHONUNBUFFERED = "1"
$py = "python"
# Do not treat Python stderr progress banners as terminating errors.
$PSNativeCommandUseErrorActionPreference = $false

function Invoke-DriveRepairStep {
    param([string]$Name, [string[]]$ArgList)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    $outFile = Join-Path $LabRoot "metrics\$Name.json"
    $timeFile = Join-Path $LabRoot "metrics\$Name.time.txt"
    $argLine = ($ArgList | ForEach-Object {
        if ($_ -match '\s') { '"' + ($_ -replace '"','`"') + '"' } else { $_ }
    }) -join ' '
    # Merge stdout/stderr into the metrics file without PowerShell ErrorRecords.
    cmd /c "`"$py`" -m driverepair_desktop $argLine > `"$outFile`" 2>&1"
    $code = $LASTEXITCODE
    "elapsed_s=$([math]::Round($sw.Elapsed.TotalSeconds,2)) exit=$code" | Set-Content $timeFile
    Write-Host ("$Name done exit=$code elapsed=$([math]::Round($sw.Elapsed.TotalSeconds,2))s")
    return $code
}

"lab_start=$(Get-Date -Format o) device=$Device identity=$IdentityHint patient_volume=E:" |
    Set-Content (Join-Path $LabRoot "LAB_RUN.txt")

Invoke-DriveRepairStep "00_list" @("list","--json") | Out-Null
Invoke-DriveRepairStep "01_health" @("health","--device",$Device,"--json") | Out-Null
Invoke-DriveRepairStep "02_monitor" @(
    "monitor-external","--device",$Device,"--expect-fingerprint",$IdentityHint,
    "--state",(Join-Path $LabRoot "monitor\history.json"),"--json"
) | Out-Null
Invoke-DriveRepairStep "03_scan_triage" @("scan","--device",$Device,"--mode","triage","--samples","128","--json") | Out-Null
Invoke-DriveRepairStep "04_scan_sample" @("scan","--device",$Device,"--mode","sample","--samples","64","--chunk-mib","1","--json") | Out-Null
Invoke-DriveRepairStep "05_benchmark" @("benchmark-external","--device",$Device,"--mode","sample","--samples","64","--chunk-mib","8","--ack-risk","--json") | Out-Null

$image = Join-Path $LabRoot "images\physicaldrive2_multipass.img"
if (-not (Test-Path $image) -or ((Get-Item $image).Length -lt 1MB)) {
    Invoke-DriveRepairStep "06_rescue_multipass" @(
        "rescue-external","--device",$Device,"--output",$image,"--ack-risk","--multi-pass","--chunk-mib","8","--json"
    ) | Out-Null
} else {
    "skip existing image length=$((Get-Item $image).Length)" | Set-Content (Join-Path $LabRoot "metrics\06_rescue_multipass.time.txt")
}

if ((Test-Path $image) -and ((Get-Item $image).Length -gt 1MB)) {
    Invoke-DriveRepairStep "07_detect_filesystems" @("detect-filesystems","--image",$image,"--json") | Out-Null
    Invoke-DriveRepairStep "08_inspect_encryption" @("inspect-encryption","--image",$image,"--json") | Out-Null
    Invoke-DriveRepairStep "09_evidence" @(
        "evidence-image","--image",$image,"--output",(Join-Path $LabRoot "recovery\evidence.json"),"--json"
    ) | Out-Null
    $recoverOut = Join-Path $LabRoot "recovery\recover_auto"
    if (-not (Test-Path $recoverOut)) {
        Invoke-DriveRepairStep "10_recover_image" @(
            "recover-image","--image",$image,"--output-dir",$recoverOut,"--mode","auto","--max-files","50","--max-file-mib","64","--json"
        ) | Out-Null
    }
}

$journal = Join-Path $LabRoot "journal\adaptive_disk"
Invoke-DriveRepairStep "11_refresh_adaptive" @(
    "refresh-external","--device",$Device,"--journal",$journal,"--mode","adaptive",
    "--journal-backend","disk","--adaptive-samples","64","--chunk-mib","1",
    "--confirm-identity",$IdentityHint,
    "--ack-risk","--ack-destructive","--ack-no-backup","--ack-data-loss-risk",
    "--ack-usb-bridge-risk","--ack-unvalidated-hardware",
    "--smart-deltas","--after-run","keep","--json"
) | Out-Null

"lab_end=$(Get-Date -Format o)" | Add-Content (Join-Path $LabRoot "LAB_RUN.txt")
Write-Host "Lab finished. Results under $LabRoot" -ForegroundColor Green
