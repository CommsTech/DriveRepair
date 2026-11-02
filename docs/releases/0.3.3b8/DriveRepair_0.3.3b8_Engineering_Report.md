# DriveRepair 0.3.3b8 — Engineering report
**Date:** 2026-11-02  
**Source:** `DriveRepair-main(10).zip` supplied by owner  
**Release judgment:** Engineering beta candidate only. **Not certified for physical-drive repair or public deployment on valuable disks.**

## What the new logs established

- Windows `Get-Disk`, CIM and WMIC discovery timed out before a Full Repair could start. A repair can't safely proceed without authoritative device identity; this is separate from media-recovery logic.
- Earlier Quick Repair covered approximately 0.014% of a 1 TB disk and repeatedly sampled similar spots. The requested new contract is **at least 10% unique-address coverage**, randomly stratified across the whole address space, with a fresh recorded seed on each physical-drive session.
- Prior Full Repair encountered I/O errors including WinError **1117**. The OS reports an I/O failure; this alone cannot distinguish defective media, USB dock, power, storage driver, or controller failure.
- Manufacturer datasheet identifies **Seagate ST1000LM048 = SMR**, not CMR. Automatic writes on adjacent logical regions could cause expensive internal band rewrites and cannot be equated with smoothing a physical platter defect.

## Source changes implemented

1. Added `media_profiles.py` with strict evidence-scoped profiles for exact manufacturer-identified SMR models, explicitly confirmed CMR, reported SATA SSD/HDD, NVMe and unknown media; USB is not considered a recording technology. SMART `rotation_rate` and NVMe protocol fields can provide additional read-only medium evidence.
2. Guided Quick Repair now targets **>=10% unique logical-address coverage**. It selects random offsets within address strata and sorts them for reduced seeking. Sampling seeds vary across physical sessions and are recorded in scan results; image tests can remain reproducible. A 1 TB quick pass means about 100 GB of source reads, not an instant check.
3. Full Repair uses a short, read-only transfer-size calibration and existing adaptive scan scheduling: increase on good areas, defer errors and retry bounded smaller reads. An initial failure stops calibration; source data isn't rewritten just because an I/O request failed.
4. Improved telemetry: counts unique sampled addresses separately from total read attempts, including re-probes. A truncated triage error map explicitly blocks uninformed writes.
5. Added read-only immediate-left/right region qualification around eligible target extents. No adjacent rewrites happen by default. Advanced `--recording cmr --rewrite-neighbors` can append independently reread CMR neighbor extents to the existing verified/journaled transaction only when the user explicitly authorizes destructive maintenance. SMR, SSD, NVMe and unidentified-media neighbor writes remain disabled.
6. Scan chunks can be large for throughput, but the repair planner uses **<=1 MiB targeted write extents**. Media selection alone does not authorize writes.
7. Windows physical-device re-identification first attempts a bounded single-disk `Get-Disk -Number N` query, instead of always enumerating all disks. Fail closed if the command still hangs; never use cached GUI inventory as authority for a write. Collected scans are returned with `repair_blocked_identity_recheck` if post-scan verification fails.
8. Simplified the main desktop workflow by collapsing most expert controls, displaying identified medium/profile text, retaining separate staged selection and the bottom Start/Stop action, and removing the disabled “Install SMART tools” button when installation is already detected.
9. Independent opt-in anomaly-history metadata can now be saved even with a RAM-only **sector journal**. History contains only offsets and classifications, not sector/file contents. Without that opt-in, RAM-only mode writes no recovery image or journal and supports no crash resume.
10. Updated README, desktop instructions, changelog, Gitea CI version references and `docs/MEDIA_AWARE_SCANNING_0.3.3b8.md`.

## Verification completed

- Full GUI-enabled regression suite on Linux under Xvfb: **264 tests run; 261 passed; 3 skipped** (platform-specific). No real disks accessed by the tests.
- Portable zip application and Python wheel generated successfully with the repository's build script.
- Packaged `care-image --mode quick` smoke test on a synthetic 64 MiB image: reported **25% unique coverage**, exceeding the 10% minimum; correctly reported no eligible target (no write).
- Packaged `care-image --mode full` smoke test on the same image: reported **100% coverage**, with read-only initial calibration and no unnecessary rewrite.
- Additional tests cover known SMR/unknown/SSD/NVMe classification, exact 10% address coverage on simulated 1 TB and 12 TB geometries, varying/reproducible sample seeds, Windows selected-disk system-drive rejection, isolated WinError 1117 handling, early read calibration, both adjacent read windows, and avoidance of error-overlapping windows.
- ZIP patch verified with `git apply --check` against the **exact original uploaded ZIP**. Source package excludes old generated firmware `target` build trees but retains actual bootloader sources.

### Artifact hashes

- `DriveRepair-0.3.3b8.pyz`: `221663c8b18ba335a419e82a35111558736f65b548dc658493468f8ecd84c612`
- `driverepair_desktop-0.3.3b8-py3-none-any.whl`: `f9cebc0ed0bff277850a29c721244ad2994d49499a9a68965918da54aaa01866`
- `DriveRepair_0.3.3b8_Media_Aware_Upgrade.patch`: `5051dae6101fc229c1d1690443ea7e623de4439f448115a4a24712277fdce59b`

## Known remaining issues / release gates

- The user-provided Windows USB dock was **not connected** to this environment. A bounded single-disk PowerShell query may still time out if Windows storage APIs or the bridge are stalled; full native Win32 storage discovery and fault-injection are future work.
- Media-detection confidence differs by interface. Most unknown USB drives remain `unknown` unless manufacturer model or accessible SMART data identify recording type. A true SMR-capable path needs physical qualification on several device-managed and host-managed variants.
- No automated end-to-end **scan → repair batch → revisit errors → next batch** loop was added. This release improves scheduling and persistent hints, not an autonomous rewrite loop.
- No reliable data-completeness, uncorrupted file-content, or “better than new” claim can follow from a successful readback comparison. Software cannot reverse platter scratches, mechanical defects or accumulated NAND wear.
- The simple-mode GUI is improved but **is still Tkinter**; this is not a complete native-Windows/macOS redesign or usability certification. Real display-scale, accessibility and novice-user studies are outstanding.
- Rust native compilation and integration, BIOS/UEFI live boot, macOS raw-device write safety, and firmware update support are not verified.
- For public beta: test safe disconnect handling, power loss, identity collisions, USB timeout behavior, crash journaling and correctness against sacrificial real CMR/SMR/SSD/NVMe hardware. Benchmark recovery quality against known-good tools under identical conditions.

## Selected manufacturer / API references

- Seagate BarraCuda 2.5 datasheet (ST1000LM048 SMR): https://www.seagate.com/www-content/datasheets/pdfs/barracuda-2-5-DS1907-3-2005US-en_CA.pdf
- Drive-managed SMR performance and internal write management: https://www.seagate.com/files/www-content/solutions-content/it-professionals/_shared/docs/smr-requires-new-data-management-usenix-login-feldman-gibson.pdf
- Microsoft storage-property identification: https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ne-winioctl-storage_property_id

**No physical drive was modified. Nothing was pushed to Gitea.**
