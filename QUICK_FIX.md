# Quick Fix for UEFI Build Error
## DriveRepair by commstech v0.0.1

## The Problem

Error: `can't find crate for 'core'` when building UEFI bootloader.

## Quick Fix Steps

1. **Check Rust Version** (must be 1.70+):
   ```powershell
   rustc --version
   ```

2. **Update Rust if needed**:
   ```powershell
   rustup update stable
   ```

3. **Reinstall UEFI targets**:
   ```powershell
   rustup target remove x86_64-unknown-uefi
   rustup target remove aarch64-unknown-uefi
   rustup target add x86_64-unknown-uefi
   rustup target add aarch64-unknown-uefi
   ```

4. **Clean and rebuild**:
   ```powershell
   cd src\boot\uefi
   cargo clean
   cd ..\..
   cargo build --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release
   ```

5. **If still failing, try nightly**:
   ```powershell
   rustup toolchain install nightly
   rustup target add x86_64-unknown-uefi --toolchain nightly
   cargo +nightly build --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release
   ```

## Most Likely Solution

The target needs to be reinstalled. Run:

```powershell
rustup target remove x86_64-unknown-uefi
rustup target add x86_64-unknown-uefi
```

Then try building again.

