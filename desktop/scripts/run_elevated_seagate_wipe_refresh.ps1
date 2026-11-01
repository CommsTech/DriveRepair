# Elevated: Wipe Seagate ST1000LM048 (Disk 2) then FULL in-place media refresh.
# Journal/metrics NEVER on the patient — only on D:\DriveRepairLab\...
# Launch: Start-Process powershell -Verb RunAs -File <this> ...
param(
    [string]$Device = "windows:PhysicalDrive2",
    [string]$IdentityHint = "138b614ad5ea",
    [int]$DiskNumber = 2,
    [string]$LabRoot = "",
    [ValidateSet("full", "adaptive")][string]$RefreshMode = "full",
    [int]$ChunkMiB = 1
)

$ErrorActionPreference = "Continue"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Desktop = Join-Path $Root "desktop"
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "Administrator required for wipe + physical refresh." }

if (-not $LabRoot) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $LabRoot = "D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_$stamp"
}
New-Item -ItemType Directory -Force -Path $LabRoot,
    (Join-Path $LabRoot "metrics"),
    (Join-Path $LabRoot "journal"),
    (Join-Path $LabRoot "monitor") | Out-Null

Set-Location $Desktop
$env:PYTHONPATH = $Desktop
$env:PYTHONUNBUFFERED = "1"
$env:DRIVEREPAIR_FORCE_TTY_DASHBOARD = "1"
$PSNativeCommandUseErrorActionPreference = $false
$py = "python"

function Invoke-Step {
    param([string]$Name, [string[]]$ArgList)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    $outFile = Join-Path $LabRoot "metrics\$Name.json"
    $timeFile = Join-Path $LabRoot "metrics\$Name.time.txt"
    $argLine = ($ArgList | ForEach-Object {
        if ($_ -match '\s') { '"' + ($_ -replace '"', '`"') + '"' } else { $_ }
    }) -join ' '
    cmd /c "`"$py`" -m driverepair_desktop $argLine > `"$outFile`" 2>&1"
    $code = $LASTEXITCODE
    "elapsed_s=$([math]::Round($sw.Elapsed.TotalSeconds, 2)) exit=$code" | Set-Content $timeFile
    Write-Host ("$Name done exit=$code elapsed=$([math]::Round($sw.Elapsed.TotalSeconds, 2))s")
    return $code
}

"lab_start=$(Get-Date -Format o) device=$Device identity=$IdentityHint disk=$DiskNumber mode=$RefreshMode wipe=Clear-Disk" |
    Set-Content (Join-Path $LabRoot "LAB_RUN.txt")

# --- Identity gate ---
Write-Host "=== 00_identity ===" -ForegroundColor Cyan
$disk = Get-Disk -Number $DiskNumber -ErrorAction Stop
if ($disk.FriendlyName -notmatch 'ST1000LM') {
    throw "Refusing wipe: Disk $DiskNumber model='$($disk.FriendlyName)' is not ST1000LM*"
}
if ($disk.BusType -ne 'USB') {
    throw "Refusing wipe: Disk $DiskNumber BusType=$($disk.BusType) (expected USB dock patient)"
}
if ([int64]$disk.Size -lt 900GB -or [int64]$disk.Size -gt 1100GB) {
    throw "Refusing wipe: Disk $DiskNumber size=$($disk.Size) outside 1TB expected band"
}
$listOut = Join-Path $LabRoot "metrics\00_list.json"
# Keep human banner on stderr out of the JSON file (cmd 2>&1 polluted ConvertFrom-Json).
cmd /c "`"$py`" -m driverepair_desktop list --json > `"$listOut`" 2> `"$LabRoot\metrics\00_list.err.txt`""
$rawList = Get-Content $listOut -Raw
# Tolerate accidental trailing noise: take from first '[' through last ']'.
$start = $rawList.IndexOf('[')
$end = $rawList.LastIndexOf(']')
if ($start -lt 0 -or $end -lt $start) {
    throw "list --json produced no JSON array; see metrics\00_list.json"
}
$listJson = $rawList.Substring($start, $end - $start + 1) | ConvertFrom-Json
$match = @($listJson | Where-Object { $_.id -eq $Device -and $_.identity_hint -eq $IdentityHint })
if (-not $match) {
    throw "list --json does not show $Device with identity_hint=$IdentityHint; aborting wipe"
}
"identity_ok model=$($disk.FriendlyName) size=$($disk.Size)" |
    Set-Content (Join-Path $LabRoot "metrics\00_identity.time.txt")

# --- Wipe partitions / filesystem (destructive) ---
Write-Host "=== 01_wipe Clear-Disk ===" -ForegroundColor Yellow
$wipeSw = [Diagnostics.Stopwatch]::StartNew()
try {
    # Offline any volumes with letters first (should already be letterless).
    Get-Partition -DiskNumber $DiskNumber -ErrorAction SilentlyContinue |
        Where-Object { $_.DriveLetter } |
        ForEach-Object {
            Write-Host "Removing access path letter $($_.DriveLetter):"
            Remove-PartitionAccessPath -DiskNumber $DiskNumber -PartitionNumber $_.PartitionNumber `
                -AccessPath "$($_.DriveLetter):\" -ErrorAction SilentlyContinue
        }
    Clear-Disk -Number $DiskNumber -RemoveData -RemoveOEM -Confirm:$false -ErrorAction Stop
    "wipe=ok elapsed_s=$([math]::Round($wipeSw.Elapsed.TotalSeconds, 2))" |
        Set-Content (Join-Path $LabRoot "metrics\01_wipe.time.txt")
    Write-Host "Clear-Disk completed."
} catch {
    "wipe=FAIL err=$($_.Exception.Message)" |
        Set-Content (Join-Path $LabRoot "metrics\01_wipe.time.txt")
    throw
}
Get-Disk -Number $DiskNumber | Format-List Number, FriendlyName, PartitionStyle, Size, OperationalStatus |
    Out-String | Set-Content (Join-Path $LabRoot "metrics\01_wipe_disk.txt")

# Re-confirm identity after wipe (USB re-enumeration can flap).
Start-Sleep -Seconds 3
$post = cmd /c "`"$py`" -m driverepair_desktop list --json"
$post | Set-Content (Join-Path $LabRoot "metrics\01b_list_after_wipe.json")
$postObj = $post | ConvertFrom-Json
$still = @($postObj | Where-Object { $_.id -eq $Device })
if (-not $still) {
    throw "Patient disappeared from list after wipe; check dock connection"
}
if ($still[0].identity_hint -ne $IdentityHint) {
    Write-Host "WARNING: identity_hint changed $($IdentityHint) -> $($still[0].identity_hint); updating confirm target" -ForegroundColor Yellow
    $IdentityHint = $still[0].identity_hint
    "identity_hint_after_wipe=$IdentityHint" | Add-Content (Join-Path $LabRoot "LAB_RUN.txt")
}

Invoke-Step "02_health" @("health", "--device", $Device, "--json") | Out-Null
Invoke-Step "03_monitor" @(
    "monitor-external", "--device", $Device, "--expect-fingerprint", $IdentityHint,
    "--state", (Join-Path $LabRoot "monitor\history.json"), "--json"
) | Out-Null

# --- Full / adaptive in-place media refresh (same-bytes rewrite) ---
$journal = Join-Path $LabRoot "journal\media_refresh"
Write-Host "=== 04_refresh_$RefreshMode ===" -ForegroundColor Cyan
Write-Host "Journal: $journal"
Write-Host "This is DESTRUCTIVE in-place rewrite of readable sectors. 1TB USB can take many hours."
$refreshArgs = @(
    "refresh-external",
    "--device", $Device,
    "--journal", $journal,
    "--mode", $RefreshMode,
    "--journal-backend", "disk",
    "--chunk-mib", "$ChunkMiB",
    "--confirm-identity", $IdentityHint,
    "--ack-risk", "--ack-destructive", "--ack-no-backup", "--ack-data-loss-risk",
    "--ack-usb-bridge-risk", "--ack-unvalidated-hardware",
    "--smart-deltas",
    "--after-run", "keep",
    "--progress-jsonl",
    "--no-live-dashboard",
    "--json"
)
if ($RefreshMode -eq "adaptive") {
    $refreshArgs += @("--adaptive-samples", "128", "--slow-multiplier", "2.0")
}
$code = Invoke-Step "04_refresh_$RefreshMode" $refreshArgs

# Post metrics (best-effort; may take a while)
Invoke-Step "05_health_after" @("health", "--device", $Device, "--json") | Out-Null
Invoke-Step "06_benchmark_after" @(
    "benchmark-external", "--device", $Device, "--mode", "sample",
    "--samples", "64", "--chunk-mib", "8", "--ack-risk", "--json"
) | Out-Null

"lab_end=$(Get-Date -Format o) refresh_exit=$code" | Add-Content (Join-Path $LabRoot "LAB_RUN.txt")
Write-Host "Wipe+refresh finished exit=$code. Results under $LabRoot" -ForegroundColor Green
exit $code
