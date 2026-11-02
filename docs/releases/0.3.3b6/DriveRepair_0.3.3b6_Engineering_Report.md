# DriveRepair 0.3.3b6 — Maintenance/firmware and read-error investigation

**Date:** 2026-11-02  
**Baseline:** `/mnt/data/DriveRepair_0.3.3b5_Error_Aware_Source.zip` (previous development snapshot)  
**Disposition:** `PRIVATE_HARDWARE_TESTING_ONLY` — not certified for public, destructive physical-drive operations.

## Current-drive evidence (supplied Windows tests)

- Device: ST1000LM048 USB-attached 1 TB hard drive, `windows:PhysicalDrive2` in the screenshots.
- Quick Repair examined 138,108,928 bytes (~0.0138% surface coverage); reported refreshing and verifying 1,794,048 bytes at two locations near the ends. A successful readback is *not* proof of recovered original file correctness or mechanical health.
- Full Scan reported multiple slow 4 MiB ranges (latency typically ~125–860 ms, 31 ms median). The earlier supplied run described **147 slow regions**; exact counts vary across logs.
- Full Scan stopped at offset `77561069568`, length `4194304`, `OSError errno=22`, with ~7.75% of surface examined. Both offset and length are divisible by 4096. This suggests a request/access/driver/bridge problem is possible, **not** proof of a bad LBA. The native `winerror` and controlled smaller-request behavior are needed to distinguish causes.
- No software mechanism was verified for flattening physical platter indentations. The supported concepts are magnetic data refresh and firmware-controlled defect reallocation.

## Changes made

1. **Bounded read-only region probe** (`desktop/driverepair_desktop/diagnostics.py` and CLI `probe-region`). Works with the selected, freshly revalidated whole drive and checks its 12-character fingerprint. A 4 MiB request may be subdivided into smaller requests (default 32 reads total, 8 MiB maximum initial extent). Data written to the original disk: **zero**. The result includes observed per-request hashes; these hashes are only *observations*, not proof of original correctness.
2. **More transparent scan errors** (`scanner.py`): report native `winerror` when present and mark `errno=22` as an unproven media failure. This doesn't change raw write authorization.
3. **Read-only firmware inventory** (`maintenance.py`, CLI `firmware-info`): obtains firmware revision using Windows storage information or optional smartctl. Always returns `update_available: NOT_CHECKED`; no download, flash, update or vendor-version inference. Vendor lookup links are informational.
4. **Windows native storage optimization advisory** (`maintenance.py`, CLI `optimize-volume`): validates physical disk-to-volume mapping; recommends HDD defrag, SSD retrim, or analysis/avoid based on Windows media type and volume filesystem. Default does not execute any optimization. Expert execution requires distinct `--execute`, `--ack-optimization-risk`, matching identity fingerprint and a qualifying SMART/volume health snapshot. There is no home-grown defrag algorithm. Unsupported/unknown media and unhealthy/system volumes cannot be optimized through this path.
5. **Remembers non-sensitive GUI preferences** (`preferences.py` and `gui.py`): repair policy, journal choice, dashboard visibility. New user default is durable disk journaling; volatile RAM can be selected and remembered. Every destructive acknowledgment remains per-operation and is never persisted. No serials, patient data, prior disk IDs, destination paths or file contents are saved to preferences.
6. **GUI integration:** new buttons for firmware info, optimization advice, and bounded failed-offset investigation; grouped to fit laptop-sized windows. Existing rescue and repair paths are preserved unchanged.
7. **Documentation/version and CI:** revised README, desktop README, changelog, maintenance guide, version `0.3.3b6`, and updated CI zipapp smoke-test filename.

## Verification actually run

- Syntax compilation of desktop package: **passed**.
- GUI-enabled Python test suite under Xvfb: **242 run, 239 passed, 3 skipped**; newly added tests cover option sanitization, saved preferences, read budgets, read request sizing, unknown firmware status, mismatch/system-volume rejection, and safe optimizer gating.
- Package builder (headless suite): **234 run, 230 passed, 4 skipped**, exit code 0. Wheel and portable zipapp produced.
- Packaged GUI workflow regression: **10 tests passed** under Xvfb; portable help screens tested for newly added `firmware-info` and `probe-region`.
- Git patch created against the exact source baseline, `git apply --check` passed, applied patch round-trip compared with the working source.
- **Not performed:** live Windows test on the ST1000LM048, actual firmware reporting or vendor-version lookup, Windows defragmentation/TRIM, any real drive I/O, BIOS/UEFI boot, Rust compilation, proprietary algorithm reverse engineering, physical surface tests.

## Recommended next test on the user's Windows laptop

Use the fresh `identity_hint` obtained from `list --json` and run a **read-only** bounded probe of byte offset `77561069568` (4 MiB). No fresh rewrite or destructive zero operation should be performed at this offset. Compare results from the current USB dock and another cable/port/dock if possible. Obtain SMART before and after; repeat only within the constrained reads budget. Stop if transport or drive identity becomes unstable.

```powershell
python .\DriveRepair-0.3.3b6.pyz list --json
python .\DriveRepair-0.3.3b6.pyz probe-region --device windows:PhysicalDrive2 `
  --offset 77561069568 --length 4194304 --max-reads 32 `
  --confirm-identity YOUR_CURRENT_IDENTITY_HINT --ack-read-stress --json
```

Firmware inventory only:

```powershell
python .\DriveRepair-0.3.3b6.pyz firmware-info --device windows:PhysicalDrive2 --json
```

**Do not defragment or update firmware on this problematic patient disk just to see whether errors disappear.** First preserve irreplaceable data. SMART may be masked by the dock, and a firmware update may itself make data inaccessible. Do not equate full-surface readback with a healthy drive or guaranteed future reliability.

## Source references

- Vendor media-read/refresh description: https://www.grc.com/sr/faq.htm
- Seagate sector reallocation: https://www.seagate.com/manuals/software/seatools-bootable/help-topic-bad-sector-found/
- Seagate firmware updates and warnings: https://www.seagate.com/support/kb/firmware-updates-for-seagate-products-207931en/
- Microsoft Optimize-Volume: https://learn.microsoft.com/powershell/module/storage/optimize-volume
- Microsoft drive firmware update precautions: https://learn.microsoft.com/en-us/windows-server/storage/update-firmware

**Important:** Performance superiority, full compatibility, long-term media reliability, and physical wear reversal remain **NOT_PROVEN**. No changes have been pushed to Gitea.
