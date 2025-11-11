# Reverse Engineering Tools Setup

## Tools Needed

### 1. Ghidra (Recommended)
- **Type**: Free, open-source reverse engineering framework
- **Platform**: Cross-platform (Windows, Linux, macOS)
- **Download**: https://ghidra-sre.org/
- **Installation**: Extract ZIP, run ghidraRun.bat
- **Use Case**: Primary tool for binary analysis

### 2. radare2 (Alternative)
- **Type**: Free, open-source reverse engineering framework
- **Platform**: Cross-platform, command-line
- **Download**: https://github.com/radareorg/radare2/releases
- **Installation**: Extract and add to PATH
- **Use Case**: Command-line analysis, automation

### 3. IDA Pro (Optional, Commercial)
- **Type**: Commercial reverse engineering tool
- **Platform**: Windows, Linux, macOS
- **Use Case**: Advanced analysis (if available)

## Installation Steps

### Ghidra Installation
1. Download Ghidra from https://ghidra-sre.org/
2. Extract to `C:\Program Files\Ghidra` or similar
3. Run `ghidraRun.bat` to start
4. Create new project
5. Import SPINRITE.EXE
6. Analyze for x86 architecture

### radare2 Installation (Windows)
1. Download from GitHub releases
2. Extract to `C:\tools\r2` or similar
3. Add to PATH
4. Run: `r2 SPINRITE.EXE`

## Analysis Workflow

1. **Import Binary**
   - Load SPINRITE.EXE into disassembler
   - Select appropriate architecture (x86 16-bit or 32-bit)

2. **Initial Analysis**
   - Auto-analyze binary
   - Identify entry points
   - Map out function structure

3. **Key Areas to Analyze**
   - Disk access functions (INT 13h calls)
   - Port I/O operations (0x1F0, 0x170)
   - LBA addressing implementation
   - Error recovery mechanisms
   - Surface scanning algorithms

4. **Documentation**
   - Document findings in REVERSE_ENGINEERING.md
   - Extract algorithm pseudocode
   - Note 1TB limitation implementation

## Commands

### Ghidra
- Open Ghidra
- Create new project
- Import SPINRITE.EXE
- Auto-analyze
- Search for INT 13h calls
- Search for port I/O

### radare2
```bash
r2 SPINRITE.EXE
aa                    # Auto-analyze
pdf @main             # Disassemble main function
/a INT 13h            # Search for INT 13h
/a inb 0x1F0          # Search for port I/O
```

