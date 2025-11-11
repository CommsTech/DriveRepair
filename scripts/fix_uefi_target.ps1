# PowerShell script to diagnose and fix UEFI target installation issues
# DriveRepair by commstech v0.0.1

Write-Host "UEFI Target Diagnostic and Fix Script" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Rust version
Write-Host "Step 1: Checking Rust version..." -ForegroundColor Yellow
$rustVersion = rustc --version
Write-Host "  $rustVersion" -ForegroundColor White

# Step 2: Check default toolchain
Write-Host ""
Write-Host "Step 2: Checking default toolchain..." -ForegroundColor Yellow
$defaultToolchain = rustup show default
Write-Host "  $defaultToolchain" -ForegroundColor White

# Step 3: Check if target is installed
Write-Host ""
Write-Host "Step 3: Checking UEFI target installation..." -ForegroundColor Yellow
$installedTargets = rustup target list --installed
$uefiTargets = $installedTargets | Select-String "uefi"

if ($uefiTargets) {
    Write-Host "  Found UEFI targets:" -ForegroundColor Green
    foreach ($target in $uefiTargets) {
        Write-Host "    $target" -ForegroundColor White
    }
} else {
    Write-Host "  No UEFI targets found!" -ForegroundColor Red
}

# Step 4: Try to verify target installation
Write-Host ""
Write-Host "Step 4: Verifying target installation..." -ForegroundColor Yellow

# Remove and reinstall with explicit toolchain
Write-Host "  Removing x86_64-unknown-uefi..." -ForegroundColor Cyan
rustup target remove x86_64-unknown-uefi 2>&1 | Out-Null

Write-Host "  Installing x86_64-unknown-uefi..." -ForegroundColor Cyan
$installOutput = rustup target add x86_64-unknown-uefi 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Target installed successfully" -ForegroundColor Green
} else {
    Write-Host "  Installation output: $installOutput" -ForegroundColor Yellow
}

# Step 5: Test compilation
Write-Host ""
Write-Host "Step 5: Testing target compilation..." -ForegroundColor Yellow

# Create a minimal test file
$testDir = "target\uefi_test"
New-Item -ItemType Directory -Path $testDir -Force | Out-Null

$testCargo = @"
[package]
name = "uefi-test"
version = "0.1.0"
edition = "2021"

[dependencies]
"@

Set-Content -Path "$testDir\Cargo.toml" -Value $testCargo

$testMain = @"
#![no_std]
#![no_main]

fn main() {}
"@

New-Item -ItemType Directory -Path "$testDir\src" -Force | Out-Null
Set-Content -Path "$testDir\src\main.rs" -Value $testMain

Write-Host "  Building test project..." -ForegroundColor Cyan
$buildOutput = cargo build --manifest-path "$testDir\Cargo.toml" --target x86_64-unknown-uefi 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "  Test build successful! Target is working." -ForegroundColor Green
    Remove-Item -Path $testDir -Recurse -Force
} else {
    Write-Host "  Test build failed. Error:" -ForegroundColor Red
    Write-Host $buildOutput -ForegroundColor Yellow
    
    Write-Host ""
    Write-Host "Step 6: Trying alternative fix..." -ForegroundColor Yellow
    Write-Host "  Updating rustup..." -ForegroundColor Cyan
    rustup update stable 2>&1 | Out-Null
    
    Write-Host "  Reinstalling target..." -ForegroundColor Cyan
    rustup target remove x86_64-unknown-uefi 2>&1 | Out-Null
    rustup target add x86_64-unknown-uefi 2>&1 | Out-Null
    
    Write-Host "  Please try building again:" -ForegroundColor Yellow
    Write-Host "    cargo build --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release" -ForegroundColor White
}

Write-Host ""
Write-Host "Diagnostic complete!" -ForegroundColor Cyan

