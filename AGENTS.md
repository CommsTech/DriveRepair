# DriveRepair agent orientation (short by design)

Start here; don't preload the full documentation tree into agent context.

- **Project/runtime:** `architecture.md`, `desktop/README.md`, `README.md`.
- **Current status (not a release certificate):** `status.md`, `docs/RELEASE_STATUS.md`.
- **Hardware write safety:** `SECURITY.md`, `docs/USB_REPAIR_PREFLIGHT_B17.md`, `desktop/driverepair_desktop/repair_readiness.py`, `desktop/driverepair_desktop/repair_routes.py`. UI approval never grants an engine write permit.
- **Windows USB devices / physical-drive access:** `docs/WINDOWS_VOLUME_ACCESS_AND_STOP_0.3.3b13.md`, `desktop/driverepair_desktop/health.py`, `scripts/qa_readonly_triage.ps1`.
- **Debian recovery ISO:** `scripts/build_live_iso.sh`, `scripts/check_live_iso.sh`, `scripts/smoke_live_iso.py`, `docs/QUALIFICATION_GATES.md`; bundled copies under `desktop/driverepair_desktop/boot_resources/` MUST agree.
- **Cold storage / SHA-256:** `desktop/driverepair_desktop/cold_storage.py`, `desktop/tests/`.
- **Reviewer judgment, not implementation instructions:** `CODING_STANDARDS.md`.

Checks, from repository root:

```sh
python scripts/check_release_hygiene.py
cd desktop && python -m pytest -q tests
# Rust if toolchain exists: cargo fmt --check && cargo test --features 'std,alloc' --lib
```

Before handing off: run available tests, state explicitly which platform tests were skipped, do not interpret successful synthetic tests as physical-drive or ISO boot qualification, use `python scripts/create_clean_source_archive.py --output /path/outside/repo.zip`, and supply a normal Git patch against the exact source revision. Never run destructive device tests on irreplaceable media.
