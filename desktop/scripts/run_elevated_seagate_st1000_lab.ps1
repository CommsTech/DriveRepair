# Elevated PRIVATE TEST lab — Seagate ST1000LM048 1TB on USB dock = PhysicalDrive2.
# Outputs NEVER go on the patient. Metrics/images/journals on D:.
# Launch: Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',<this>
param(
    [string]$Device = "windows:PhysicalDrive2",
    [string]$IdentityHint = "138b614ad5ea",
    [string]$LabRoot = "D:\DriveRepairLab\seagate_st1000lm048_1tb_20261101_151108",
    [int]$MaxRescueChunks = 32
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
    (Join-Path $LabRoot "integrity"),
    (Join-Path $LabRoot "recovery") | Out-Null

Set-Location $Desktop
$env:PYTHONPATH = $Desktop
$env:PYTHONUNBUFFERED = "1"
$py = "python"
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
    cmd /c "`"$py`" -m driverepair_desktop $argLine > `"$outFile`" 2>&1"
    $code = $LASTEXITCODE
    "elapsed_s=$([math]::Round($sw.Elapsed.TotalSeconds,2)) exit=$code" | Set-Content $timeFile
    Write-Host ("$Name done exit=$code elapsed=$([math]::Round($sw.Elapsed.TotalSeconds,2))s")
    return $code
}

"lab_start=$(Get-Date -Format o) device=$Device identity=$IdentityHint model=ST1000LM048-2E7172 max_rescue_chunks=$MaxRescueChunks" |
    Set-Content (Join-Path $LabRoot "LAB_RUN.txt")

Invoke-DriveRepairStep "00_list" @("list","--json") | Out-Null
Invoke-DriveRepairStep "01_health" @("health","--device",$Device,"--json") | Out-Null
Invoke-DriveRepairStep "02_monitor" @(
    "monitor-external","--device",$Device,"--expect-fingerprint",$IdentityHint,
    "--state",(Join-Path $LabRoot "monitor\history.json"),"--json"
) | Out-Null
Invoke-DriveRepairStep "03_scan_triage" @("scan","--device",$Device,"--mode","triage","--samples","128","--json") | Out-Null
Invoke-DriveRepairStep "04_scan_sample" @("scan","--device",$Device,"--mode","sample","--samples","64","--chunk-mib","1","--json") | Out-Null
Invoke-DriveRepairStep "05_benchmark" @(
    "benchmark-external","--device",$Device,"--mode","sample","--samples","64","--chunk-mib","8","--ack-risk","--json"
) | Out-Null

$image = Join-Path $LabRoot "images\physicaldrive2_bounded.img"
# No --multi-pass here: first-pass only, hard-capped by --max-chunks.
# Windows rescue images use sparse SetEndOfFile so the full logical size
# does not zero-fill D: before the chunk bound stops.
Invoke-DriveRepairStep "06_rescue_bounded" @(
    "rescue-external","--device",$Device,"--output",$image,"--ack-risk",
    "--chunk-mib","1","--max-chunks",$MaxRescueChunks.ToString(),"--json"
) | Out-Null

$journalPath = "$image.rescue.json"
$recoveredBytes = 0
if (Test-Path $journalPath) {
    try {
        $recoveredBytes = [int64]((Get-Content $journalPath -Raw | ConvertFrom-Json).recovered_bytes)
    } catch { $recoveredBytes = 0 }
}

if ((Test-Path $image) -and ($recoveredBytes -gt 1MB)) {
    # Work on a compact prefix only. The sparse logical image may be ~1TB;
    # hashing / Copy-Item of that size hangs Windows labs for hours.
    $prefix = Join-Path $LabRoot "images\physicaldrive2_bounded_prefix.img"
    $prefixLen = [Math]::Min($recoveredBytes, [int64]$MaxRescueChunks * 1MB)
    $in = [IO.File]::Open($image, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        $out = [IO.File]::Create($prefix)
        try {
            $buf = New-Object byte[] (1MB)
            $left = $prefixLen
            while ($left -gt 0) {
                $n = $in.Read($buf, 0, [int][Math]::Min($buf.Length, $left))
                if ($n -le 0) { break }
                $out.Write($buf, 0, $n)
                $left -= $n
            }
        } finally { $out.Close() }
    } finally { $in.Close() }
    "prefix_bytes=$prefixLen source_recovered=$recoveredBytes" |
        Set-Content (Join-Path $LabRoot "metrics\06b_prefix.time.txt")

    Invoke-DriveRepairStep "07_detect_filesystems" @("detect-filesystems","--image",$prefix,"--json") | Out-Null
    Invoke-DriveRepairStep "08_inspect_encryption" @("inspect-encryption","--image",$prefix,"--json") | Out-Null
    Invoke-DriveRepairStep "09_evidence" @(
        "evidence-image","--image",$prefix,"--output",(Join-Path $LabRoot "recovery\evidence.json"),"--json"
    ) | Out-Null

    # Integrity workflow (0.3.3b1): baseline → corrupt copy → audit → restore-copy
    $integ = Join-Path $LabRoot "integrity"
    $baseline = Join-Path $integ "baseline.img"
    $candidate = Join-Path $integ "candidate_bitflip.img"
    $manifest = Join-Path $integ "baseline.json"
    $restored = Join-Path $integ "restored.img"
    Copy-Item $prefix $baseline -Force
    Copy-Item $prefix $candidate -Force
    Invoke-DriveRepairStep "10_integrity_baseline" @(
        "integrity-baseline","--image",$baseline,"--output",$manifest,"--chunk-mib","1","--json"
    ) | Out-Null

    # Flip one bit in the second MiB so audit must localize a single chunk.
    $fs = [IO.File]::Open($candidate, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite)
    try {
        $fs.Seek(1MB + 17, [IO.SeekOrigin]::Begin) | Out-Null
        $b = New-Object byte[] 1
        [void]$fs.Read($b, 0, 1)
        $fs.Seek(-1, [IO.SeekOrigin]::Current) | Out-Null
        $b[0] = $b[0] -bxor 0x01
        $fs.Write($b, 0, 1)
    } finally { $fs.Close() }

    Invoke-DriveRepairStep "11_integrity_audit" @(
        "integrity-audit","--image",$candidate,"--manifest",$manifest,"--json"
    ) | Out-Null
    Invoke-DriveRepairStep "12_integrity_restore" @(
        "integrity-restore-copy","--image",$candidate,"--reference",$baseline,
        "--manifest",$manifest,"--output",$restored,"--ack-same-snapshot","--json"
    ) | Out-Null
    Invoke-DriveRepairStep "13_verify_restored" @(
        "verify-images","--image",$baseline,"--output",$restored,"--json"
    ) | Out-Null
}

"lab_end=$(Get-Date -Format o)" | Add-Content (Join-Path $LabRoot "LAB_RUN.txt")
Write-Host "Lab finished. Results under $LabRoot" -ForegroundColor Green
