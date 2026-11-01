# Project status — November 1, 2026

**Version:** 0.3.0b1 experimental engineering beta candidate, source patch based on the supplied `DriveRepair-main(3).zip` snapshot.

The desktop project currently has source implementations for external-disk inventory, read-only diagnostic scans, bounded image rescue, FAT32 selective deleted-file recovery, optional Sleuth Kit deleted-file selection, limited file carving, corrupted ZIP salvage, ext-image clone-only repair, SMART monitoring, synthetic in-place-refresh tests, and a high-contrast guided Tk interface. A separate no-dependency Rust core for regular-file rescue has been added but cannot be claimed built or validated without Cargo and cross-platform CI.

**What is NOT supported/certified:** universal raw disk repair, secure government sanitization, automatic media rejuvenation, firmware recovery, byte-exact recovery of overwritten data, universal filesystem undelete, dependable bootable rescue ISO, certified forensic chain of custody, faster-than-competitors claims. The original boot code remains experimental; physical USB disconnect/power-loss validation must still be completed.

See `PUBLIC_BETA_GATES.md` and `BENCHMARK_PROTOCOL.md` before release. Old reports in `docs/release-readiness/` document older snapshots and do not supersede this status.
