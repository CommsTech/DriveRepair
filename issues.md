# Open issues / gaps

1. No physical-disk validation (disconnection, power-loss, destination isolation, timeouts).
2. External rescue still Linux-only; Windows/macOS need equivalent safe acquisition paths.
3. FAT32 undelete is contiguous/unallocated only; no NTFS/exFAT/APFS/ext4 undelete.
4. ext repair requires host `e2fsck` and only mutates clones; mocked on Windows without the tool.
5. GUI needs real Windows/macOS/Linux smoke testing; no signed native installers.
6. Media-refresh engine intentionally not enabled.
7. Public release gates (hardware matrix, license review, bootable environment) unmet.
