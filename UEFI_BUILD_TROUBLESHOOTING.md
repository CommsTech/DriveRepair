# UEFI Build Troubleshooting
## DriveRepair by commstech v0.0.1

## Error: "can't find crate for `core`"

This error indicates that the Rust compiler cannot find the `core` library for the UEFI target. This is a common issue with UEFI targets.

## Solutions

### Solution 1: Reinstall the Target

```powershell
# Remove and reinstall the target
rustup target remove x86_64-unknown-uefi
rustup target add x86_64-unknown-uefi

# Also for ARM64
rustup target remove aarch64-unknown-uefi
rustup target add aarch64-unknown-uefi
```

### Solution 2: Update Rust Toolchain

The UEFI target requires Rust 1.70 or later. Check your version:

```powershell
rustc --version
```

If your version is too old, update:

```powershell
rustup update stable
```

### Solution 3: Use Nightly Toolchain (if needed)

Some UEFI features may require nightly. Install and use nightly:

```powershell
rustup toolchain install nightly
rustup target add x86_64-unknown-uefi --toolchain nightly
cargo +nightly build --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release
```

### Solution 4: Verify Target Installation

Check if the target is properly installed:

```powershell
rustup target list --installed | Select-String "uefi"
```

You should see:
- `x86_64-unknown-uefi`
- `aarch64-unknown-uefi`

### Solution 5: Clean Build

Sometimes a clean build helps:

```powershell
cd src\boot\uefi
cargo clean
cargo build --target x86_64-unknown-uefi --release
```

### Solution 6: Check Rust Version Compatibility

The `uefi` crate version 0.30 requires:
- Rust 1.70 or later
- Properly installed UEFI targets

Verify compatibility:

```powershell
rustc --version
# Should show 1.70.0 or later
```

### Solution 7: Alternative UEFI Crate

If the issue persists, you might need to use a different UEFI crate version. Check the `uefi` crate documentation for version requirements.

## Current Configuration

- **UEFI crate**: `uefi = "0.30"`
- **UEFI services**: `uefi-services = "0.22"`
- **Target**: `x86_64-unknown-uefi` and `aarch64-unknown-uefi`
- **Edition**: `2021`

## Next Steps

1. Try Solution 1 (reinstall target) first
2. If that doesn't work, try Solution 2 (update Rust)
3. If still failing, try Solution 3 (nightly toolchain)
4. Check the `uefi` crate documentation for any known issues

## Additional Resources

- UEFI crate documentation: https://docs.rs/uefi/
- Rust UEFI target: https://github.com/rust-osdev/uefi-rs
- Rust toolchain installation: https://rustup.rs/

