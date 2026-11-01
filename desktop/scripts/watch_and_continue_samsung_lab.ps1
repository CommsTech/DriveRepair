# Watch multipass rescue growth; when complete, run post-rescue lab steps 07-11.
# Safe to run alongside the elevated lab already in 06_rescue_multipass.
param(
    [string]$Device = "windows:PhysicalDrive2",
    [string]$IdentityHint = "e5a0dfacc956",
    [string]$LabRoot = "D:\DriveRepairLab\samsung_pm841_256_20261101",
    [long]$TargetBytes = 256060514304
)

$ErrorActionPreference = "Continue"
$PSNativeCommandUseErrorActionPreference = $false
$Desktop = Split-Path $PSScriptRoot -Parent
Set-Location $Desktop
$env:PYTHONPATH = $Desktop
$env:PYTHONUNBUFFERED = "1"
$img = Join-Path $LabRoot "images\physicaldrive2_multipass.img"
$progressLog = Join-Path $LabRoot "metrics\06_rescue_progress.jsonl"
$doneMarker = Join-Path $LabRoot "metrics\06_rescue_multipass.time.txt"

function Invoke-Step([string]$Name, [string[]]$ArgList) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    $outFile = Join-Path $LabRoot "metrics\$Name.json"
    $argLine = ($ArgList | ForEach-Object {
        if ($_ -match '\s') { '"' + ($_ -replace '"','`"') + '"' } else { $_ }
    }) -join ' '
    cmd /c "python -m driverepair_desktop $argLine > `"$outFile`" 2>&1"
    $code = $LASTEXITCODE
    "elapsed_s=$([math]::Round($sw.Elapsed.TotalSeconds,2)) exit=$code" |
        Set-Content (Join-Path $LabRoot "metrics\$Name.time.txt")
    Write-Host "$Name done exit=$code"
    return $code
}

Write-Host "Watching rescue image: $img" -ForegroundColor Cyan
$stable = 0
while ($true) {
    if (-not (Test-Path $img)) {
        Start-Sleep -Seconds 10
        continue
    }
    $len = (Get-Item $img).Length
    $pct = [math]::Round(100.0 * $len / $TargetBytes, 2)
    $line = "{`"ts`":`"$(Get-Date -Format o)`",`"bytes`":$len,`"pct`":$pct}"
    Add-Content -Path $progressLog -Value $line
    Write-Host ("rescue {0:N2} GiB / {1:N2} GiB ({2}%)" -f ($len/1GB), ($TargetBytes/1GB), $pct)
    $py = Get-Process -Id 15844 -ErrorAction SilentlyContinue
    if ($len -ge $TargetBytes) { break }
    if (-not $py -and (Test-Path $doneMarker)) { break }
    if (-not $py) {
        $stable++
        if ($stable -ge 3) {
            Write-Host "Rescue python exited; image at $pct% — continuing with what we have / resume if incomplete."
            break
        }
    } else { $stable = 0 }
    Start-Sleep -Seconds 30
}

# If incomplete, resume multipass rather than abandoning.
$len = if (Test-Path $img) { (Get-Item $img).Length } else { 0 }
if ($len -lt $TargetBytes) {
    Write-Host "Resuming rescue-external (--resume) to finish remaining bytes..." -ForegroundColor Yellow
    # Preallocated sparse/full image may already exist; resume into same path.
    Invoke-Step "06_rescue_multipass_resume" @(
        "rescue-external","--device",$Device,"--output",$img,"--ack-risk","--resume","--chunk-mib","8","--json"
    ) | Out-Null
    # multi-pass second stage if map indicates missing
    if (Test-Path ($img + ".rescue.json")) {
        Invoke-Step "06_rescue_multipass_retry" @(
            "rescue-external","--device",$Device,"--output",$img,"--ack-risk","--resume","--retry-missing","--chunk-mib","8","--json"
        ) | Out-Null
    }
} elseif (-not (Test-Path $doneMarker)) {
    "elapsed_s=watched exit=0 note=image_reached_target" | Set-Content $doneMarker
}

if ((Test-Path $img) -and ((Get-Item $img).Length -gt 1MB)) {
    Invoke-Step "07_detect_filesystems" @("detect-filesystems","--image",$img,"--json") | Out-Null
    Invoke-Step "08_inspect_encryption" @("inspect-encryption","--image",$img,"--json") | Out-Null
    $ev = Join-Path $LabRoot "recovery\evidence.json"
    if (-not (Test-Path $ev)) {
        Invoke-Step "09_evidence" @("evidence-image","--image",$img,"--output",$ev,"--json") | Out-Null
    }
    $recoverOut = Join-Path $LabRoot "recovery\recover_auto"
    if (-not (Test-Path $recoverOut)) {
        Invoke-Step "10_recover_image" @(
            "recover-image","--image",$img,"--output-dir",$recoverOut,"--mode","auto","--max-files","50","--max-file-mib","64","--json"
        ) | Out-Null
    }
}

$journal = Join-Path $LabRoot "journal\adaptive_disk"
if (-not (Test-Path (Join-Path $LabRoot "metrics\11_refresh_adaptive.time.txt"))) {
    Invoke-Step "11_refresh_adaptive" @(
        "refresh-external","--device",$Device,"--journal",$journal,"--mode","adaptive",
        "--journal-backend","disk","--adaptive-samples","64","--chunk-mib","1",
        "--confirm-identity",$IdentityHint,
        "--ack-risk","--ack-destructive","--ack-no-backup","--ack-data-loss-risk",
        "--ack-usb-bridge-risk","--ack-unvalidated-hardware",
        "--smart-deltas","--after-run","keep","--json"
    ) | Out-Null
}

"lab_continue_end=$(Get-Date -Format o)" | Add-Content (Join-Path $LabRoot "LAB_RUN.txt")
Write-Host "Post-rescue lab steps finished." -ForegroundColor Green
