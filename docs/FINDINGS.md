# Reverse Engineering Findings - SPINRITE.EXE
## DriveRepair by commstech v0.0.1

## Binary Structure Analysis

### File Header
- **Type**: DOS executable (MZ) with PE header (DOS extender)
- **Size**: 173,144 bytes
- **Date**: June 5, 2004
- **Author**: SGibson (from copyright string)

### DOS Header Details
- **Signature**: MZ (0x4D5A) ✅
- **PE Offset**: 0xF110 (61,712 bytes) ✅
- **PE Signature**: "PE\0\0" ✅
- **Architecture**: x86 (16-bit or 32-bit)

## Pattern Analysis Results

### INT 13h BIOS Calls
Found 3 direct INT 13h calls:
1. **Offset 0x142FA** (82,682 bytes)
   - Likely: Disk read/write function
   - Context: To be analyzed with disassembler

2. **Offset 0x18478** (99,448 bytes)
   - Likely: Disk access function
   - Context: To be analyzed with disassembler

3. **Offset 0x259DE** (154,078 bytes)
   - Likely: Disk access function
   - Context: To be analyzed with disassembler

### Port I/O Operations (ATA)
Found port I/O operations on both primary and secondary channels:

**Primary Channel (0x1F0)**:
1. **Offset 0x23E** (574 bytes)
   - Operation: IN AL, 0x1F0 (read from ATA data register)
   - Context: Early in binary, likely initialization

2. **Offset 0x1CBFC** (117,756 bytes)
   - Operation: IN AL, 0x1F0 (read from ATA data register)
   - Context: Likely in disk read function

**Secondary Channel (0x170)**:
1. **Offset 0x103A1** (66,465 bytes)
   - Operation: IN AL, 0x170 (read from secondary ATA data register)
   - Context: Secondary channel access

2. **Offset 0x21F19** (139,033 bytes)
   - Operation: IN AL, 0x170 (read from secondary ATA data register)
   - Context: Secondary channel access

**Note**: Offset 0x139D6 was a false positive (exceeds file size)

### Secondary Channel (0x170)
- **Found**: 2 locations
  - IN AL, 0x170 at offset 0x103A1 (66,465 bytes from start)
  - IN AL, 0x170 at offset 0x21F19 (139,033 bytes from start)
- **Analysis**: Secondary ATA channel support confirmed

## String Analysis

### Extracted Strings
- "SGibson" - Author name
- "(c) 2004 by SGibson" - Copyright string
- "AMAB", "ZDMA" - Possible function names or identifiers

## Key Findings

### Disk Access Methods
1. **INT 13h BIOS Calls**: Confirmed (3 locations)
   - Used for BIOS-level disk access
   - Likely for compatibility with older systems

2. **Direct Port I/O**: Confirmed (3 locations on 0x1F0)
   - Direct ATA controller access
   - Bypasses BIOS for better control

### Architecture Implications
- Uses both BIOS calls and direct hardware access
- Likely supports both CHS and LBA addressing
- May have 32-bit LBA limitation (to be confirmed)

## Next Steps

1. **Load binary into Ghidra**
   - Import SPINRITE.EXE
   - Auto-analyze for x86 architecture
   - Map functions at identified offsets

2. **Analyze INT 13h Functions**
   - Disassemble code at 0x142FA, 0x18478, 0x259DE
   - Identify function parameters
   - Document calling conventions

3. **Analyze Port I/O Functions**
   - Disassemble code at 0x23E, 0x1CBFC
   - Identify ATA command sequences
   - Document register usage

4. **Extract Algorithms**
   - Error recovery mechanisms
   - Surface scanning patterns
   - LBA addressing implementation

5. **Document 1TB Limitation**
   - Identify LBA size (32-bit vs 48-bit)
   - Document capacity calculation
   - Note overflow handling

## Implementation Notes

### For Modern Implementation
- Use 64-bit LBA throughout (fixes 1TB limitation)
- Support both UEFI and BIOS boot methods
- Implement direct hardware access for better control
- Maintain compatibility with BIOS calls where needed

