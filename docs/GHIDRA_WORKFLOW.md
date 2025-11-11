# Ghidra Analysis Workflow
## DriveRepair by commstech v0.0.1

## Quick Start Guide

### 1. Launch Ghidra
```powershell
cd tools\ghidra_11.4.2_PUBLIC
.\ghidraRun.bat
```

### 2. Create New Project
1. File → New Project
2. Select "Non-Shared Project"
3. Name: "DriveRepair"
4. Location: Choose project directory

### 3. Import SPINRITE.EXE
1. File → Import File
2. Navigate to project root: `C:\Users\commstech\Github\DriveRepair\SPINRITE.EXE`
3. Click "OK"
4. Select language: **x86:LE:32:default** (32-bit little-endian x86)
   - Alternative: **x86:LE:16:default** if 16-bit DOS
5. Click "OK"

### 4. Auto-Analyze
1. Analysis → Auto Analyze 'SPINRITE.EXE'
2. Check all analysis options
3. Click "Analyze"
4. Wait for analysis to complete

## Key Locations to Analyze

### INT 13h Calls
1. **Offset 0x142FA** (82,682 bytes)
   - Right-click → Go To → Enter offset: `0x142FA`
   - Analyze function containing this call
   - Document parameters and calling convention

2. **Offset 0x18478** (99,448 bytes)
   - Go To: `0x18478`
   - Analyze context and function

3. **Offset 0x259DE** (154,078 bytes)
   - Go To: `0x259DE`
   - Analyze context and function

### Port I/O Operations

#### Primary Channel (0x1F0)
1. **Offset 0x23E** (574 bytes)
   - Go To: `0x23E`
   - Analyze: IN AL, 0x1F0
   - Context: Early initialization

2. **Offset 0x1CBFC** (117,756 bytes)
   - Go To: `0x1CBFC`
   - Analyze: IN AL, 0x1F0
   - Context: Disk read function

#### Secondary Channel (0x170)
1. **Offset 0x103A1** (66,465 bytes)
   - Go To: `0x103A1`
   - Analyze: IN AL, 0x170

2. **Offset 0x21F19** (139,033 bytes)
   - Go To: `0x21F19`
   - Analyze: IN AL, 0x170

## Analysis Checklist

### For Each INT 13h Call
- [ ] Identify function containing the call
- [ ] Document function name (rename if needed)
- [ ] Identify parameters (AH register value, drive number, etc.)
- [ ] Document calling convention
- [ ] Trace data flow (buffers, sector addresses)
- [ ] Identify error handling

### For Each Port I/O Operation
- [ ] Identify function containing the operation
- [ ] Document ATA command sequence
- [ ] Identify register usage (AL, AH, etc.)
- [ ] Document port addresses (0x1F0-0x1F7, 0x170-0x177)
- [ ] Trace data flow
- [ ] Identify error handling

### General Analysis
- [ ] Map all disk access functions
- [ ] Document LBA addressing implementation
- [ ] Identify 32-bit vs 48-bit LBA usage
- [ ] Document error recovery mechanisms
- [ ] Extract surface scanning algorithms
- [ ] Document SMART command implementation

## Search Strategies

### Search for INT 13h
1. Search → For Instructions
2. Pattern: `CD 13` (INT 13h opcode)
3. Review all matches

### Search for Port I/O
1. Search → For Instructions
2. Pattern: `E4 F0` (IN AL, 0x1F0)
3. Pattern: `E6 F0` (OUT 0x1F0, AL)
4. Pattern: `E4 70` (IN AL, 0x170)
5. Pattern: `E6 70` (OUT 0x170, AL)

### Search for Strings
1. Search → For Strings
2. Look for: "DISK", "SECTOR", "LBA", "ERROR", "READ", "WRITE"

### Search for Functions
1. Window → Defined Strings
2. Look for function names or identifiers
3. Cross-reference with code

## Documentation Workflow

### For Each Function Analyzed
1. **Rename Function**: Right-click → Rename Function
   - Use descriptive name: `read_sector_int13h`, `ata_port_read`, etc.

2. **Add Comments**: 
   - Right-click → Set Comment
   - Document purpose, parameters, return values

3. **Create Function Signature**:
   - Edit → Function → Edit Function Signature
   - Document parameters and return type

4. **Export Findings**:
   - Document in `docs/ANALYSIS_LOG.md`
   - Add pseudocode to `docs/REVERSE_ENGINEERING.md`
   - Update `docs/FINDINGS.md`

## Key Algorithms to Extract

### 1. Sector Read Algorithm
- Function entry point
- Parameter setup
- INT 13h or port I/O sequence
- Data transfer
- Error handling
- Return value

### 2. LBA Addressing
- How LBA is calculated
- 32-bit vs 48-bit usage
- CHS conversion (if any)
- Address packet structure

### 3. Error Recovery
- Retry logic
- Delay mechanisms
- Error detection
- Recovery strategies

### 4. Surface Scanning
- Scan pattern implementation
- Sector ordering
- Progress tracking

## Tips

1. **Use Bookmarks**: Bookmark important functions and locations
2. **Create Structures**: Define data structures for ATA commands, INT 13h packets
3. **Cross-Reference**: Use XRefs to find all callers of functions
4. **Decompile**: Use Decompiler window to see C-like pseudocode
5. **Export**: Export function listings and disassembly

## Next Steps After Analysis

1. Document all findings in `docs/ANALYSIS_LOG.md`
2. Extract algorithms to `docs/REVERSE_ENGINEERING.md`
3. Implement findings in Rust code
4. Update `docs/STATUS.md` with progress
5. Commit and push to git

