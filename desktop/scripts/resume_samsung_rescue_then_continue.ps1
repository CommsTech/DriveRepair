# Resume Samsung PM841 rescue with throttled identity checks, then post-image steps.
param(
    [string]$Device = "windows:PhysicalDrive2",
    [string]$IdentityHint = "e5a0dfacc956",
    [string]$LabRoot = "D:\DriveRepairLab\samsung_pm841_256_20261101"
)

$ErrorActionPreference = "Continue"
$PSNativeCommandUseErrorActionPreference = $false
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "Administrator required." }

$Desktop = "C:\Users\commstech\Github\DriveRepair\desktop"
Set-Location $Desktop
$env:PYTHONPATH = $Desktop
$env:PYTHONUNBUFFERED = "1"
$img = Join-Path $LabRoot "images\physicaldrive2_multipass.img"

function Invoke-Step([string]$Name, [string[]]$ArgList) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    $outFile = Join-Path $LabRoot "metrics\$Name.json"
    $errFile = Join-Path $LabRoot "metrics\$Name.stderr.log"
    # Live stderr to console (RESCUE progress), stdout captured for JSON metrics.
    $p = Start-Process -FilePath "python" -ArgumentList (@("-u","-m","driverepair_desktop") + $ArgList) `
        -WorkingDirectory $Desktop -NoNewWindow -PassThru `
        -RedirectStandardOutput $outFile -RedirectStandardError $errFile
    # Tail stderr live so the Admin window is not blank during long rescues.
    $tailJob = Start-Job -ScriptBlock {
        param($path)
        $pos = 0
        while ($true) {
            Start-Sleep -Milliseconds 500
            if (-not (Test-Path $path)) { continue }
            $fs = [IO.File]::Open($path, 'Open', 'Read', 'ReadWrite')
            try {
                $fs.Seek($pos, 'Begin') | Out-Null
                $sr = New-Object IO.StreamReader($fs)
                $chunk = $sr.ReadToEnd()
                $pos = $fs.Position
                if ($chunk) { Write-Output $chunk }
            } finally { $fs.Close() }
        }
    } -ArgumentList $errFile
    while (-not $p.HasExited) {
        Receive-Job $tailJob | ForEach-Object { Write-Host $_ -NoNewline }
        Start-Sleep -Milliseconds 400
    }
    Start-Sleep -Milliseconds 600
    Receive-Job $tailJob | ForEach-Object { Write-Host $_ -NoNewline }
    Stop-Job $tailJob -ErrorAction SilentlyContinue
    Remove-Job $tailJob -Force -ErrorAction SilentlyContinue
    $code = $p.ExitCode
    "elapsed_s=$([math]::Round($sw.Elapsed.TotalSeconds,2)) exit=$code" |
        Set-Content (Join-Path $LabRoot "metrics\$Name.time.txt")
    Write-Host ""
    Write-Host "$Name done exit=$code elapsed=$([math]::Round($sw.Elapsed.TotalSeconds,2))s"
    return $code
}

"resume_start=$(Get-Date -Format o)" | Add-Content (Join-Path $LabRoot "LAB_RUN.txt")

# Stop any leftover hung first-pass process before resume (best-effort).
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.CommandLine -match 'driverepair_desktop' -and $_.CommandLine -match 'rescue-external'
} | ForEach-Object {
    Write-Host "Stopping prior rescue pid=$($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

Invoke-Step "06_rescue_resume" @(
    "rescue-external","--device",$Device,"--output",$img,
    "--ack-risk","--resume","--chunk-mib","8","--json"
) | Out-Null

# Multipass retry pass if map still has missing ranges
$map = Get-Content ($img + ".rescue.json") -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
if ($map -and $map.missing_ranges -and @($map.missing_ranges).Count -gt 0) {
    Invoke-Step "06_rescue_retry_missing" @(
        "rescue-external","--device",$Device,"--output",$img,
        "--ack-risk","--resume","--retry-missing","--chunk-mib","8","--json"
    ) | Out-Null
}

Invoke-Step "07_detect_filesystems" @("detect-filesystems","--image",$img,"--json") | Out-Null
Invoke-Step "08_inspect_encryption" @("inspect-encryption","--image",$img,"--json") | Out-Null
$ev = Join-Path $LabRoot "recovery\evidence.json"
if (-not (Test-Path $ev)) {
    Invoke-Step "09_evidence" @("evidence-image","--image",$img,"--output",$ev,"--json") | Out-Null
}
$recoverOut = Join-Path $LabRoot "recovery\recover_auto"
if (-not (Test-Path $recoverOut)) {
    Invoke-Step "10_recover_image" @(
        "recover-image","--image",$img,"--output-dir",$recoverOut,
        "--mode","auto","--max-files","50","--max-file-mib","64","--json"
    ) | Out-Null
}

$journal = Join-Path $LabRoot "journal\adaptive_disk"
Invoke-Step "11_refresh_adaptive" @(
    "refresh-external","--device",$Device,"--journal",$journal,"--mode","adaptive",
    "--journal-backend","disk","--adaptive-samples","64","--chunk-mib","1",
    "--confirm-identity",$IdentityHint,
    "--ack-risk","--ack-destructive","--ack-no-backup","--ack-data-loss-risk",
    "--ack-usb-bridge-risk","--ack-unvalidated-hardware",
    "--smart-deltas","--after-run","keep","--json"
) | Out-Null

"resume_end=$(Get-Date -Format o)" | Add-Content (Join-Path $LabRoot "LAB_RUN.txt")
Write-Host "Resume+continue finished." -ForegroundColor Green
