# DriveRepair 0.3.1b1 — Last-Resort Single-Drive Update

## Purpose
Enable **separately confirmed, experimental in-place refresh** of consistently readable sectors on an **unmounted internal disk** from trusted Linux live media, when no second disk / image destination is available. The rolling journal lives in a checked Linux RAM filesystem (`tmpfs`/`ramfs`) and protects only the region being rewritten; it is **NOT** an image/backup or a method to recover already-unreadable or overwritten file contents.

## Source basis
`DriveRepair_0.3.1b1_Final_Candidate_Source.zip`. Seven changed/new source and documentation files, patch verified with `git apply --check` against this exact archive.

## Implementation
- New `refresh-system` command routed into the existing transactional `refresh_media` implementation.
- Restricts system-disk writes to Linux, requires `--ack-offline-system`, exact device fingerprint, `--ack-risk`, `--ack-destructive`, `--ack-no-backup`, `--ack-data-loss-risk`, `--ack-unvalidated-hardware`. RAM mode adds `--ack-volatile-journal`, a real RAM filesystem, and live UPS/battery preflight.
- Requeries disk identity before and after opening and inside operation callbacks, checks duplicate serials across **all** Linux disks; existing no-mount/no-holders and exclusive raw block device checks remain in effect.
- USB devices also require bridge and protected-dock-power acknowledgments.
- Added GUI under **Recover OS drive** with two-step RAM/power preflight and a manually confirmed adaptive refresh action. No automatic writes or scheduled refresh.
- Updated one-drive and refresh safety documentation, and added fail-closed tests plus a RAM-journal torn-write/resume synthetic test.

## Validation performed in this container
- Python desktop test suite: **156 total, 155 passed, 1 Windows-only skipped**.
- Portable `.pyz` build: **PASS** (help smoke test) from `scripts/build_desktop.py`.
- Wheel build: **PASS** (`pip wheel --no-build-isolation`).
- Syntax compilation: **PASS** for desktop source.
- Patch application check against exact prior archive: **PASS**.
- **No physical disks opened or written**, no hardware disconnect/power loss tests, no boot ISO validation, no performance or data-restoration superiority benchmark.

## Known limitations / nonclaims
- A rolling RAM journal protects **one current chunk**, not a full drive. 12 TB cannot fit in ordinary laptop RAM. A lost RAM journal during a partial patient write can leave irrecoverable corruption.
- UPS telemetry does not guarantee the disk or USB dock stays powered or that the OS and RAM remain healthy.
- Successful matching reads only prove repeatability; preexisting corruption remains corrupt. Unreadable/inconsistent regions are not rewritten and do not become restored.
- Resuming requires original journal bytes to still be available in the same live OS. A host reboot loses the RAM journal and may remove the possibility of a safe rollback.
- Only Linux offline-system refresh is exposed. Windows/macOS live OS-drive refresh remains unsupported.
- Raw hardware writes still await independent risk assessment, sacrificial USB/power-failure experiments and release approval. Do not use this mode on irreplaceable data.

## Patch changes
```
 CHANGELOG.md                                     |  12 ++
 desktop/README.md                                |  13 ++
 desktop/driverepair_desktop/cli.py               |  44 ++++--
 desktop/driverepair_desktop/gui.py               |  71 +++++++++-
 desktop/tests/test_last_resort_system_refresh.py | 173 +++++++++++++++++++++++
 docs/IN_PLACE_MEDIA_REFRESH.md                   |  23 +++
 docs/ONE_DRIVE_RECOVERY.md                       |  78 ++++++++++
 7 files changed, 400 insertions(+), 14 deletions(-)
```

## Suggested validation for OpenClaw/Cursor
Run `python scripts/build_desktop.py` and `python -m unittest discover -s desktop/tests -v` (with package import path configured appropriately). Verify true Linux live USB behavior on **sacrificial** SATA/USB sample disks; test interrupted writes, USB disconnect and host failure before exposing to beta users. Independently inspect the Linux `O_EXCL` and mount/holder checks, and reject cases with missing serial or duplicate bridge identity. Preserve the private/experimental release gate until validated.
