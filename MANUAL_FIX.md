# Manual Fix for UEFI Build Error
## DriveRepair by commstech v0.0.1

## The Issue

Even after installing `x86_64-unknown-uefi`, you're getting `can't find crate for 'core'`.

## Solution: Update rustup and Reinstall Target

Run these commands **in order**:

```powershell
# 1. Update rustup itself
rustup self update

# 2. Update the stable toolchain
rustup update stable

# 3. Remove the UEFI target
rustup target remove x86_64-unknown-uefi
rustup target remove aarch64-unknown-uefi

# 4. Reinstall the targets
rustup target add x86_64-unknown-uefi
rustup target add aarch64-unknown-uefi

# 5. Verify installation
rustup target list --installed | Select-String "uefi"

# 6. Try building again
cargo build --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release
```

## Alternative: Use Nightly Toolchain

If the above doesn't work, try using nightly:

```powershell
# Install nightly
rustup toolchain install nightly

# Add targets to nightly
rustup target add x86_64-unknown-uefi --toolchain nightly
rustup target add aarch64-unknown-uefi --toolchain nightly

# Build with nightly
cargo +nightly build --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release
```

## If Still Failing

Check if there's a toolchain mismatch:

```powershell
# Check which toolchain is default
rustup show default

# Check which toolchain has the target
rustup target list --toolchain stable | Select-String "uefi"
rustup target list --toolchain nightly | Select-String "uefi"

# Make sure you're using the right toolchain
rustup default stable
```

## Most Common Fix

The most common fix is updating rustup and reinstalling:

```powershell
rustup self update
rustup update stable
rustup target remove x86_64-unknown-uefi
rustup target add x86_64-unknown-uefi
```

Then try building again.

