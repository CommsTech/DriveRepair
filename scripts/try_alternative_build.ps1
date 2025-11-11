# Alternative build approach for UEFI target
# DriveRepair by commstech v0.0.1

Write-Host "Trying Alternative UEFI Build Methods" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Method 1: Check if cargo-xbuild is needed
Write-Host "Method 1: Checking if cargo-xbuild is available..." -ForegroundColor Yellow
$hasXbuild = Get-Command cargo-xbuild -ErrorAction SilentlyContinue
if ($hasXbuild) {
    Write-Host "  cargo-xbuild found!" -ForegroundColor Green
    Write-Host "  Try: cargo xbuild --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release" -ForegroundColor White
} else {
    Write-Host "  cargo-xbuild not installed" -ForegroundColor Yellow
    Write-Host "  Install with: cargo install cargo-xbuild" -ForegroundColor Cyan
}

Write-Host ""

# Method 2: Try with nightly and build-std
Write-Host "Method 2: Checking nightly toolchain..." -ForegroundColor Yellow
$hasNightly = rustup toolchain list | Select-String "nightly"
if ($hasNightly) {
    Write-Host "  Nightly toolchain found" -ForegroundColor Green
    Write-Host "  Try: cargo +nightly build -Z build-std=core --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release" -ForegroundColor White
} else {
    Write-Host "  Nightly not installed" -ForegroundColor Yellow
    Write-Host "  Install with: rustup toolchain install nightly" -ForegroundColor Cyan
}

Write-Host ""

# Method 3: Verify target installation
Write-Host "Method 3: Verifying target installation..." -ForegroundColor Yellow
$targetInfo = rustup target show x86_64-unknown-uefi 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Target information:" -ForegroundColor Green
    Write-Host $targetInfo -ForegroundColor White
} else {
    Write-Host "  Could not get target information" -ForegroundColor Red
}

Write-Host ""

# Method 4: Check sysroot
Write-Host "Method 4: Checking sysroot..." -ForegroundColor Yellow
$sysroot = rustc --print sysroot --target x86_64-unknown-uefi 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Sysroot: $sysroot" -ForegroundColor Green
    $corePath = Join-Path $sysroot "lib\rustlib\x86_64-unknown-uefi\lib\libcore*.rlib"
    if (Test-Path $corePath) {
        Write-Host "  Core library found!" -ForegroundColor Green
    } else {
        Write-Host "  Core library NOT found at: $corePath" -ForegroundColor Red
        Write-Host "  This confirms the target installation is incomplete" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Could not get sysroot: $sysroot" -ForegroundColor Red
}

Write-Host ""
Write-Host "Recommendations:" -ForegroundColor Cyan
Write-Host "  1. Try installing cargo-xbuild: cargo install cargo-xbuild" -ForegroundColor White
Write-Host "  2. Or use nightly with build-std feature" -ForegroundColor White
Write-Host "  3. Or check if there's a UEFI-specific toolchain" -ForegroundColor White

