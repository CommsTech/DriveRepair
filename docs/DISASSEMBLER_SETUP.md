# Disassembler Tools Installation Guide

## Ghidra Installation

### Manual Download (Recommended)
1. Visit: https://ghidra-sre.org/
2. Click "Download" button
3. Download latest release (ghidra_*_PUBLIC_*.zip)
4. Extract to `tools\ghidra` directory
5. Run `ghidraRun.bat` to start

### Automated Download (If Available)
```powershell
# Download latest Ghidra release
$url = "https://github.com/NationalSecurityAgency/ghidra/releases/latest/download/ghidra_11.1_PUBLIC_20241210.zip"
Invoke-WebRequest -Uri $url -OutFile "tools\ghidra.zip"
Expand-Archive -Path "tools\ghidra.zip" -DestinationPath "tools"
```

## radare2 Installation

### Windows (via Git)
```powershell
# Clone radare2 repository
git clone https://github.com/radareorg/radare2.git tools\r2
cd tools\r2
sys\install.bat
```

### Pre-built Binaries
1. Visit: https://github.com/radareorg/radare2/releases
2. Download Windows installer
3. Install to `C:\tools\r2` or similar
4. Add to PATH

## Analysis Workflow

### Using Ghidra
1. Start Ghidra: `tools\ghidra*\ghidraRun.bat`
2. Create new project: "DriveRepair"
3. Import SPINRITE.EXE
4. Select language: x86:LE:32:default (or x86:LE:16:default)
5. Auto-analyze: Analysis → Auto Analyze
6. Search for:
   - INT 13h calls
   - Port I/O (0x1F0, 0x170)
   - LBA calculations
   - Error handling

### Using radare2
```bash
# Start analysis
r2 SPINRITE.EXE

# Auto-analyze
aa

# Disassemble entry point
pdf @main

# Search for INT 13h
/a INT 13h

# Search for port I/O
/a inb 0x1F0
/a outb 0x1F0

# List functions
afl

# Disassemble function
pdf @sym.function_name
```

## Analysis Checklist

- [ ] Binary loaded into disassembler
- [ ] Architecture identified
- [ ] Entry point located
- [ ] Main function identified
- [ ] Disk access functions found
- [ ] INT 13h calls documented
- [ ] Port I/O operations documented
- [ ] LBA addressing analyzed
- [ ] Error recovery mechanisms identified
- [ ] Scan patterns documented
- [ ] 1TB limitation identified

