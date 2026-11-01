# Open issues / gaps

1. No physical-disk validation (disconnection, power-loss, destination isolation, timeouts).
2. External rescue still Linux-only; Windows/macOS need equivalent safe acquisition paths.
3. FS undelete: FAT32 + NTFS + exFAT (contiguous/simple) shipped via `recover-image`; Btrfs/ZFS/APFS/ext still RAW-only; fragmented/encrypted volumes incomplete.
4. ext repair requires host `e2fsck` and only mutates clones; mocked on Windows without the tool.
5. GUI needs real Windows/macOS/Linux smoke testing; no signed native installers; Tk is interim until Rust presentation shell.
6. Media-refresh is gated PRIVATE TEST ONLY; interrupt/USB-dock sacrificial matrix still incomplete.
7. Public release gates (hardware matrix, license review, bootable environment) unmet.
8. True acoustic sensing unavailable over USB; mechanical* remains a latency/error proxy.
9. BitLocker detection is signature-based on images; live PhysicalDrive inspect-encryption path still limited — prefer imaging then inspect.
10. PowerShell must not pipe live dashboard stderr under ErrorAction Stop (kills UI).
11. Some SanDisk SDSSDH3 500 G units on the current USB dock refuse writes (WinError 1117/121) while a third identical model passes write probe + Adaptive — treat as media/dock variance until interrupt matrix exists.
12. Mixed Repository Detective exports that include `nettech` / `Repository-Detective` rows must be filtered by `RepoFullName` before DriveRepair remediation.
