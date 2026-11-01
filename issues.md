# Open issues / gaps

1. No full physical-disk validation matrix (disconnection, power-loss, destination isolation, timeouts).
2. External rescue still Linux-primary; Windows/macOS safe acquisition paths incomplete.
3. NTFS/exFAT undelete are bounded heuristics; Btrfs/ZFS/APFS remain RAW-carve only.
4. ext repair requires host `e2fsck` and only mutates clones; mocked on Windows without the tool.
5. GUI needs real Windows/macOS/Linux smoke testing; no signed native installers; Tk interim.
6. Media-refresh interrupt/USB-dock sacrificial matrix still incomplete.
7. Public release gates (hardware matrix, license review, bootable environment) unmet.
8. Acoustic/IMU sensors are soft WATCH/STOP only; USB docks expose neither contact mic nor platter IMU.
9. BitLocker detection is signature-based on images; live PhysicalDrive inspect path still limited.
10. PowerShell must not pipe live dashboard stderr under ErrorAction Stop (kills UI).
11. Some SanDisk SDSSDH3 500 G units on the current USB dock refuse writes (WinError 1117/121).
12. Mixed Repository Detective exports must be filtered by `RepoFullName` before DriveRepair remediation.
13. OpenClaw memory embeddings (`mxbai-embed-large`) currently 404 from Cursor — continue without recall until fixed.
14. `rust/recovery-core` compiler/CI validation still pending.
