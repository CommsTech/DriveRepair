# System Architecture

## Overview
Modern drive repair tool built in Rust, supporting drives from 64GB to 20TB with UEFI/BIOS bootable USB support.

## Architecture Layers

### 1. Boot Layer
- **UEFI Bootloader**: UEFI application entry point
- **BIOS Bootloader**: Multiboot-compliant bootloader with INT 13h support
- **Hybrid Boot**: GPT partition table with protective MBR

### 2. Disk Interface Layer
Unified abstraction supporting:
- **ATA/IDE**: PIO and DMA modes
- **SATA**: AHCI controller access
- **NVMe**: PCIe-based direct controller access
- **USB**: Mass storage protocol

### 3. Core Services
- **Disk Detection**: PCI enumeration, AHCI detection, USB enumeration
- **SMART Interface**: Command interface, attribute parsing, health reporting
- **Repair Engine**: Sector reading, error correction, surface scanning, TRIM support

### 4. User Interface
- Text-based UI for bootable environment
- Drive selection interface
- Progress indicators and status reporting

## Key Design Decisions

### 64-bit LBA Addressing
- All disk operations use 64-bit LBA throughout
- Supports drives up to 2^64 sectors (effectively unlimited)
- Proper handling of 4KB sector sizes

### Modular Design
- Separate modules for each disk interface type
- Unified trait/interface for disk operations
- Pluggable repair algorithms

### Boot Compatibility
- UEFI: Native EFI application
- BIOS: Multiboot-compliant with real-mode support
- Mac: Compatibility layer for Mac hardware

## Data Flow

```
Boot → Disk Detection → Interface Selection → SMART Check → Repair Engine → UI Feedback
```

## Memory Management
- UEFI: UEFI memory allocator
- BIOS: Custom memory manager for bootable environment
- Heap allocation for dynamic structures

## Error Handling
- Retry logic for sector reads
- Error recovery mechanisms
- SMART-based predictive failure analysis

