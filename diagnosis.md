# diagnosis.md — DriveRepair Windows pathway diagnosis (2026-11-21)

Live diagnosis of the Windows diagnostic/repair pathway, using the DriveRepair
node (Alienware17R3) and the Seagate ST1000LM048 candidate (`PhysicalDrive3`,
`I:` / `DRSMR1T`, identity hint `01825bdbb561`). Read-only throughout; no
patient media was written.

## Presenting problem

Owner asked whether a Windows SMART failure leaves no way to obtain the
information needed to repair a drive. Live triage answered **no** — the app's
"SMART failure" was actually an availability problem, not a media verdict, and
Windows offers two coarser native evidence sources with clear limits.

## Findings, with evidence

### F1 — SMART unavailability was being conflated with SMART failure
- Windows health snapshot at the tip reports `smart_status_passed: null` and an
  explicit `smart_unavailable_reason`: "SMART probe failed (status bits 2:
  device open failed)... Check administrator rights, the USB dock/cable and the
  supported smartctl device type".
- `smartctl` **is** installed and found (`smartctl_available: true`), so the
  failure is an access/bridge problem, not a missing tool.
- Root cause candidates, ordered: non-elevated process token (F2), USB SAT
  passthrough refusal for this bridge, or filter-driver interference.
- Status: **diagnosed**; final discrimination requires an elevated rerun.

### F2 — Non-elevated raw access is denied and previously crashed the scan path
- `inspect-windows-access --device windows:PhysicalDrive3` (non-elevated):
  `status: raw_access_denied`, `error_code: 5`, `administrator_token: false`,
  `writes_performed: false`, exit code 2.
- Before `4d7f911`, the scan path surfaced this as a bare `WinError 5`
  traceback and gave no operator guidance (`run-log 20261121004432-2bda6d7d`).
- Fix (shipped): scans preflight raw access and fail closed with structured
  next-steps before opening any patient handle. **Verified live.**

### F3 — No intermediate native evidence existed between "Healthy" and SMART
- `Get-Disk`/`Get-PhysicalDisk` said Healthy/Online for all USB disks —
  deliberately treated as never a SMART substitute.
- `Get-StorageReliabilityCounter` (temperature, read/write error totals, wear,
  power-on hours) was available in principle but unused, and non-elevated
  queries returned nothing usable for this disk.
- Fix (shipped, `4d7f911`): health snapshots supplement SMART-unavailable
  results with reliability counters, matched to exactly one PhysicalDisk by
  number/UniqueId; ambiguous identity stays unavailable; counters are labeled
  weaker-than-SMART and never qualify writes. A warning status routes repair
  advice to `rescue_replace`.
- Status: **implemented and unit-tested**; live counter collection still needs
  an elevated session to disambiguate "elevation required" vs "bridge hides
  counters".

### F4 — Device identity is weak on this USB stack
- `Get-Disk` reports placeholder-like serials (`0000…1`, `0000…`, a control
  character) across the three USB disks. DriveRepair's identity hints
  (`01825bdbb561`, resume hint) are the actual disambiguators.
- Risk: any mapping that trusts reported serials alone can select the wrong
  physical disk. The reliability-counter supplement therefore refuses ambiguous
  matches rather than guessing — by design, an unavailable result is safer than
  a wrong one.

### F5 — `python -m driverepair_desktop.cli` silently exited 0
- The obvious module invocation produced no output and success status.
- Fix (shipped, `928d669`): `__main__` guard routed through `main()`, with
  runpy regression tests. Any CLI surface needs an entry-behavior test.

## Differential for the next elevated session

1. Run `inspect-windows-access` elevated → expect `read_only_access_available`.
2. Run SMART via smartctl `/dev/pd3` elevated → three outcomes:
   - SMART completes: real verdict. PASSED → repair candidacy may proceed
     through the gated workflow; FAILED → rescue-only.
   - Open still fails: bridge/policy refuses passthrough → trust reliability
     counters + physical check; consider another adapter/boot rescue media.
   - Counters attach with warnings → `rescue_replace` advice, no refresh.
3. Until then the candidate stays "SMART unavailable, health limited"; repair
   authorization remains NOT GRANTED (backup/disposability confirmation and
   mode selection are still outstanding owner gates).

## Environment side-findings (not app defects)

- Full `unittest discover` stalls on the busy Linux host (jbd2/fsync waits) —
  run bounded suites locally and the full pytest suite on Windows.
- Gitea CI API returns 404 → CI status unqueryable; GitHub mirror
  unauthenticated → mirror push NOT_PROVEN.
