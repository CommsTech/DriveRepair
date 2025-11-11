# Reverse Engineering Notes - SPINRITE.EXE

## File Information
- **File Name**: SPINRITE.EXE
- **Size**: 173,144 bytes (~169 KB)
- **Date**: June 5, 2004
- **SHA256**: 230BE922979B19338C7395D318317C23A003E50EC949EEDB3B8F7E7A9A6531...

## Initial Analysis

### File Type
Based on the file size and date (2004), this appears to be an older version of SpinRite, likely:
- 16-bit DOS executable, or
- 32-bit Windows/DOS executable
- Possibly a bootable floppy disk image or DOS-based utility

### Known Limitations
- **1TB Drive Limitation**: The original implementation likely uses 32-bit LBA (Logical Block Addressing)
  - 32-bit LBA = 2^32 sectors × 512 bytes = 2TB theoretical maximum
  - Practical limitations may restrict to 1TB due to:
    - CHS (Cylinder-Head-Sector) addressing limitations
    - BIOS INT 13h extensions limitations
    - 32-bit integer overflow in calculations

### Disk Access Methods (Expected)
1. **INT 13h BIOS Calls**: Primary method for older versions
   - INT 13h, AH=02h: Read sectors
   - INT 13h, AH=03h: Write sectors
   - INT 13h, AH=42h: Extended Read (LBA)
   - INT 13h, AH=43h: Extended Write (LBA)

2. **Direct Hardware Access**: For IDE/ATA drives
   - Port I/O to IDE controller registers
   - ATA command set (0x1F0-0x1F7 primary, 0x170-0x177 secondary)

3. **CHS to LBA Conversion**: May use Cylinder-Head-Sector addressing

### Algorithm Patterns (To Document)
- Low-level sector reading with retry logic
- Error correction and data recovery
- Surface scanning patterns
- SMART attribute reading
- Bad sector remapping

## Reverse Engineering Tools Needed
- Ghidra (free, cross-platform) - Recommended for initial analysis
- IDA Pro (commercial) - Advanced analysis
- radare2 (free, command-line) - Command-line disassembler
- objdump (if available) - Binary inspection
- hexdump/hex editor for binary inspection

## Binary Analysis Commands

### Using PowerShell to inspect binary
```powershell
# Get file header information
Get-Content SPINRITE.EXE -TotalCount 100 -Encoding Byte | Format-Hex

# Check for DOS header (MZ signature)
$bytes = [System.IO.File]::ReadAllBytes("SPINRITE.EXE")
$dosHeader = [System.Text.Encoding]::ASCII.GetString($bytes[0..1])
Write-Host "DOS Header: $dosHeader"  # Should be "MZ"
```

### Using Ghidra
1. Import SPINRITE.EXE
2. Analyze for x86 architecture (likely 16-bit or 32-bit)
3. Identify entry points
4. Map out disk access functions
5. Document LBA addressing implementation

### Using radare2
```bash
# Install radare2 (if available on Windows)
# Analyze binary
r2 SPINRITE.EXE
# Disassemble entry point
aa
pdf @main
# Search for disk access patterns
/a INT 13h
```

## Next Steps
1. Disassemble binary to identify entry points
2. Map out core functions and algorithms
3. Document disk access patterns
4. Identify the 1TB limitation implementation
5. Extract error recovery mechanisms
6. Document sector reading algorithms
7. Extract SMART attribute reading code
8. Document surface scanning patterns

## Notes
- This is a DOS-era utility, so it likely runs in real mode or 16-bit protected mode
- Modern implementation will need to support UEFI and 64-bit addressing
- Bootable environment will need to handle both BIOS and UEFI boot methods

