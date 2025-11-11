# Windows Build Solutions
## DriveRepair by commstech v0.0.1

## Problem

UEFI bootloader build fails on Windows with "can't find crate for 'core'".

## Solutions (No Linux Required)

### Solution 1: Use WSL (Windows Subsystem for Linux) - Easiest!

WSL lets you run Linux on Windows without a separate machine:

#### Install WSL:
```powershell
# Run PowerShell as Administrator
wsl --install

# Or if WSL is already installed, just install Ubuntu:
wsl --install -d Ubuntu
```

#### Build in WSL:
```bash
# Open WSL (Ubuntu)
cd /mnt/c/Users/commstech/Github/DriveRepair

# Install Rust in WSL
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env

# Build bootloader
rustup target add x86_64-unknown-uefi
cargo build --manifest-path src/boot/uefi/Cargo.toml --target x86_64-unknown-uefi --release

# The .efi file will be at:
# src/boot/uefi/target/x86_64-unknown-uefi/release/drive-repair-uefi.efi
```

#### Copy to Windows:
The file is already accessible from Windows at:
```
C:\Users\commstech\Github\DriveRepair\src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi
```

### Solution 2: Try Fixing Windows Build (Advanced)

Let's try one more approach to fix the Windows build:

```powershell
# Clean everything
cargo clean --manifest-path src\boot\uefi\Cargo.toml

# Try with explicit toolchain
rustup default stable
rustup target remove x86_64-unknown-uefi
rustup target add x86_64-unknown-uefi

# Try building with verbose output to see exact error
cargo build --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release -v 2>&1 | Select-Object -Last 50
```

### Solution 3: Use Docker (If WSL doesn't work)

```powershell
# Install Docker Desktop for Windows
# Then:
docker run --rm -v ${PWD}:/workspace -w /workspace rust:latest bash -c "
rustup target add x86_64-unknown-uefi && 
cargo build --manifest-path src/boot/uefi/Cargo.toml --target x86_64-unknown-uefi --release
"
```

### Solution 4: Use GitHub Actions / CI

If you have the code in a Git repository, you can use GitHub Actions or Gitea Actions to build:

1. Push code to repository
2. CI builds bootloaders automatically
3. Download the built `.efi` files from CI artifacts

## Recommended: WSL

**WSL is the easiest solution** - it's free, built into Windows, and works perfectly for this use case.

### Quick WSL Setup:

1. **Install WSL** (one command):
   ```powershell
   # Run as Administrator
   wsl --install
   ```

2. **Restart computer** (if prompted)

3. **Open WSL** (Ubuntu terminal)

4. **Build bootloader**:
   ```bash
   # Navigate to project
   cd /mnt/c/Users/commstech/Github/DriveRepair
   
   # Install Rust
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   source ~/.cargo/env
   
   # Build
   rustup target add x86_64-unknown-uefi
   cargo build --manifest-path src/boot/uefi/Cargo.toml --target x86_64-unknown-uefi --release
   ```

5. **Use the file** (already on Windows):
   ```powershell
   .\scripts\copy_bootloaders.ps1 -UsbDrive "E:" -UefiX64Path "src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi"
   ```

## Summary

- ✅ **WSL**: Easiest, no separate machine needed
- ⚠️ **Fix Windows build**: May work, but has been problematic
- ✅ **Docker**: Works but more setup
- ✅ **CI/CD**: Automatic but requires repository setup

**Recommendation: Use WSL - it's the simplest solution!**

