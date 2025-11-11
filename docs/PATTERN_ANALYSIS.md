# Binary Pattern Analysis - SPINRITE.EXE
## Initial Pattern Search Results

## INT 13h Call Analysis

### Search Method
- Pattern: 0xCD 0x13 (INT 13h instruction)
- Search through entire binary

### Results
- **INT 13h calls found**: TBD (see analysis output)
- **Locations**: TBD
- **Context**: To be analyzed with disassembler

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
- **Port I/O operations found**: TBD
- **Primary channel (0x1F0)**: TBD
- **Secondary channel (0x170)**: TBD

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

