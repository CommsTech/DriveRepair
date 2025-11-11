# Binary Pattern Analysis - SPINRITE.EXE
## Initial Pattern Search Results

## INT 13h Call Analysis

### Search Method
- Pattern: 0xCD 0x13 (INT 13h instruction)
- Search through entire binary

### Results
- **INT 13h calls found**: 3 locations
- **Locations**:
  - 0x142FA (82,682 bytes from start)
  - 0x18478 (99,448 bytes from start)
  - 0x259DE (154,078 bytes from start)
- **Context**: To be analyzed with disassembler
- **Analysis**: These are likely disk access functions

### Notes
- May use indirect calls (CALL [address])
- May use function pointers
- May be in library code

## Port I/O Analysis

### Search Method
- Pattern: 0xE4 0xF0 (IN AL, 0x1F0)
- Pattern: 0xE6 0xF0 (OUT 0x1F0, AL)
- Also check for 0x170 (secondary channel)

### Results
- **Port I/O operations found**: 3 locations
- **Primary channel (0x1F0)**:
  - IN AL, 0x1F0 at offset 0x23E (574 bytes from start)
  - OUT 0x1F0, AL at offset 0x139D6 (803,030 bytes from start - likely invalid, check)
  - IN AL, 0x1F0 at offset 0x1CBFC (117,756 bytes from start)
- **Secondary channel (0x170)**: Found 2 locations
  - IN AL, 0x170 at offset 0x103A1 (66,465 bytes from start)
  - IN AL, 0x170 at offset 0x21F19 (139,033 bytes from start)
- **Analysis**: These are direct ATA port I/O operations

### Notes
- May use different opcodes
- May use indirect addressing
- May be in library code

## String Analysis

### Extracted Strings
- To be populated from string extraction

### Potential Disk-Related Strings
- "DISK", "DRIVE", "SECTOR", "LBA", "CHS"
- Error messages
- Status messages

## Function Entry Points

### Potential Entry Points
- DOS entry point: TBD
- Main function: TBD
- Disk access functions: TBD

## Next Steps
1. Complete disassembler installation
2. Load binary for full analysis
3. Map all functions
4. Trace disk access code paths
5. Extract algorithms

