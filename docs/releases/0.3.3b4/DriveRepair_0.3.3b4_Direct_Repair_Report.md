# DriveRepair 0.3.3b4 — No-Image Direct Repair and RAM-Only Journal

**Source baseline:** User-uploaded `DriveRepair-main(8).zip`  
**Status:** Engineering prototype; unrestricted physical-media beta **NOT APPROVED**  
**Validation:** Synthetic image and mocked hardware paths only; no physical disk was modified.

## User-requested result

The former UI required users to select a recovery-image destination or a disk-backed journal before any useful maintenance could run. The updated **Diagnose / Rescue** page presents **Quick repair** and **Full repair**, plus a **Temporary region storage** selector:

- **Volatile RAM only (NO saved files)** — no image destination, no journal files, no persistent recovery checkpoint.
- **Disk journal (crash recoverable)** — bounded saved preimage on healthy separate storage; remains safer.

A separate **In-place refresh** workflow offers adaptive or full-surface read/rewrite/verify, with a `memory` journal option. The direct repair workflow is available through `care-external` (and synthetic `care-image`), without a second-drive image.

A quick repair uses a deterministic triage sample, locates suspect *slow but readable* regions, double-reads them, holds original bytes temporarily, writes back the same bytes, flushes and verifies readback. Full repair scans the entire surface before selecting suspect regions for targeted refresh. **Neither regenerates missing file bytes, repairs filesystem metadata, certifies stored bits without a trusted reference, or reverses worn physical components.** A clean scan makes zero unnecessary writes.

## Critical RAM-only tradeoff

Process-memory mode now explicitly **never writes media-refresh preimage bytes or transaction metadata to a journal file**. It cannot resume after a process restart or host shutdown. A torn write can permanently damage the active region, even if the computer has a UPS. The implementation performs one immediate bounded rollback attempt while original bytes remain in memory, then verifies. If rollback fails it reports `critical_volatile_rollback_failed`; no success status is returned. Power loss and hard process termination can prevent even that attempt.

No guarantee can be made about Windows paging, hibernation, dump files, antivirus, or other OS activity writing memory to disk. RAM-only means **DriveRepair does not create image or media-refresh journal files**, not a guarantee of zero operating-system disk writes.

## Safety controls

- Raw-media writes require explicitly selecting an external patient and confirming its device ID and fingerprint.
- Separate destructive, no-backup, data-loss, USB-dock and unvalidated-hardware risk acknowledgements are still required.
- If the patient is mounted or in use, physical writes are blocked; running-system disks are not candidates.
- Linux uses exclusive block-device opens; Windows attempts exclusive raw-disk handles and volume locking.
- Inconsistent or unreadable regions are **not** rewritten; health warnings stop targeted refresh.
- Cross-process job restart is not available with process RAM, intentionally and transparently.
- Mac hardware writes remain disabled pending exclusive-lock and hardware testing.
- External USB dock power must be considered separately from laptop power.

## Tests actually performed

1. `python scripts/build_desktop.py` — **PASS**, 211 tests run: 207 passed, four platform/display-specific skips.
2. `xvfb-run -a python -m unittest tests.test_gui_workflows -v` — **PASS, 8 GUI tests**, including visible and clickable Quick repair, Full repair and RAM-only choice.
3. `python -m unittest tests.test_ram_only_repair -v` — **PASS, 8 targeted tests**, including no journal/image artifacts, mocked external drive writes, aborted sessions, nonresumability and torn-write rollback.
4. Packaged `.pyz` full-image synthetic rewrite — **PASS**, original 1 MiB image preserved exactly after rewrite, 1 MiB verified, no journal/image output created.
5. `git apply --check` against the exact uploaded source baseline — **PASS**.
6. Wheel built offline with `pip wheel --no-build-isolation --no-deps` — **PASS**.

Test exclusions: **Windows laptop/USB dock power-loss, disconnect, mounted volume behavior, faulted real media, macOS write support, UEFI/BIOS booting, physical wear-repair efficacy and comparative benchmarks were NOT tested or certified**.

## Using the GUI

```powershell
python .\DriveRepair-0.3.3b4.pyz gui
```

1. Close any previous DriveRepair version; use the new package.
2. Choose **My external drive is slow or failing**; click **Refresh inventory** and select the drive by model, capacity, connection and identifier.
3. Choose **Volatile RAM only (NO saved files)** under temporary region storage; click **Quick repair** or **Full repair**.
4. Read warnings and enter the exact selected device ID. Elevated permissions and an offline, unused patient may be necessary on Windows.
5. To rewrite all consistently readable regions, use the separate **In-place refresh** page with **Mode = full** and **Journal = memory**. This is higher risk.
6. Do not use RAM-only on irreplaceable sole-copy data. Preserve the data to alternate storage or seek professional recovery first whenever possible.

If there is nothing safely refreshable, DriveRepair reports that no refresh was performed, rather than claiming repair.

## Release gates still outstanding

Physical Windows and Linux external-disk qualification, forced-reset/USB disconnection, power-loss with UPS telemetry, mounted-volume race tests, independent write safety audit, filesystem-specific correction, data integrity proof with trusted baselines, and formal BIOS/UEFI boot validation.

**Engineering assessment:** This change closes the missing RAM-only UI and no-image direct-refresh feature, but does **not** certify a failing disk as healthy or guarantee faster operation or successful data restoration.
