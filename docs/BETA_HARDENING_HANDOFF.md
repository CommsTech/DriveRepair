# DriveRepair beta hardening — Gitea/Cursor handoff

**Review baseline:** the user-supplied `DriveRepair-main (1)(2).zip`, project version `0.3.3b13`.
**Change status:** patch prepared locally; not merged, tagged, published, signed, or pushed to Gitea. Source version stays `0.3.3b13` and the changelog explicitly has an **Unreleased** section.
**Release recommendation:** only an **image-first controlled beta candidate** after native manual testing. **Do not distribute the standard engineering wheel or `.pyz` as a public beta.**

## Implemented and tested changes

| Area | Change | Reason / guarantee |
|---|---|---|
| Windows health classification | `windows_health_limited` returns `UNKNOWN` instead of `OK` | Coarse Windows HealthStatus without SMART attributes does not prove healthy media. Actual warnings and failures remain visible. |
| SMR identification | Match exact known model tokens, reject prefix overmatches | Prevent unsupported drive model suffixes being treated as known SMR devices. This still does **not** infer physical track geometry. |
| Scan resume | Unique private checkpoint temporary files; atomic rename, file+directory fsync where supported, sector-aligned range checks | A stale `.pending` file cannot permanently block future checkpoints; malformed saved ranges cannot be silently trusted. |
| Surface-map responsiveness | Cached exact byte coverage, sorted disjoint intervals, localized insertion/merging | Avoid repeated full interval summation and sorting; preserve *fractional* coverage for sparse/quick scans rather than marking whole regions healthy. |
| Refresh status | Distinct committed-boundary resume, durable preimage, and in-flight crash recovery fields | Memory and hybrid modes must not imply disk-journal crash safety. |
| Legacy Tk Stop | Cooperative stdin STOP for supported scan/refresh modes; disable window-close kill for active jobs | No intentional kill in the middle of an experimental physical write; read-only operations can still be terminated if required. A stuck kernel read cannot be guaranteed cancellable. |
| Qt Stop and goal | Window close requests Stop without killing active write process; public build disables guided Fix | Safer cancellation and more obvious image-first workflow. |
| Unix writer | Compare the opened special-file device ID with the path on the same device after opening | Basic path replacement race guard; **not** complete hardware serial identity proof. |
| Public candidate build | `--public-beta` creates a separate name and embeds a non-runtime-toggleable write deny policy; guards CLI and direct source-image/raw-writer constructors | The distributed candidate rejects in-place source image and physical disk rewrites and executed Windows optimization before device access. Not a signed sandbox or security boundary. |
| CI packaging test | Offline public candidate deny paths plus small image scan/rescue/status/byte-exact check | Catches release-gate regressions in the actual distributable artifact. |
| README and CHANGELOG | Present capabilities, qualified vs unqualified OS workflows, image-first quick start, accurate Unreleased changes, and known gaps | Avoid marketing engineering prototypes as a public-ready hardware repair product. |

### Automated evidence

- Local Python 3.13 `python -m unittest discover -s tests -v`: **320 tests run, 4 skipped, 0 failed or errored** after patch (baseline before changes: 310 tests, 4 skipped).
- `python -m compileall -q desktop/driverepair_desktop scripts`: **PASS**.
- `git diff --check`: **PASS**.
- `python scripts/build_desktop.py --no-wheel`: **PASS** (ordinary **engineering** zipapp, not for public distribution).
- `python scripts/build_desktop.py --public-beta --no-wheel`: **PASS**.
- `python scripts/check_public_beta.py dist/DriveRepair-0.3.3b13-public-beta.pyz`: **PASS**, tests six CLI write-deny variants, read-only 1 MiB image scan, copy-out rescue, journal status, SHA-256 equivalence. No hardware touched.
- Native Windows 10/11, macOS, Linux privileged-drive tests, Qt/Tk clickthrough on real desktops, Rust fmt/clippy/cargo build/tests, real faulty-drive benchmarks and power/USB interruption tests: **NOT PERFORMED/NOT PROVEN** in this review environment. Do not convert synthetic evidence into platform certification.

### Outstanding risks before broad public distribution

**P0: No unrestricted physical-media repair.** The physical-write path still requires independent review, checked device-handle serial identity across re-enumeration, lock/dismount correctness, and sacrificial 512e/4Kn/SMR/CMR/SSD/NVMe + USB disconnect/power-loss validation. Windows raw blocking I/O and driver cancellation behavior is unresolved. For uncertain drive health, never make source writes your first recovery action.

**P1: Native integration qualification.** Run fresh setup and UI workflows on current Windows, Linux and macOS; ensure different drive sizes, inaccessible/RAW partitions, mounted-holder conflicts, UAC/elevation, destination-full, symlink/destination alias, and active output disconnect produce clear partial/failed status without modifying patient data.

**P1: Recovery corpus correctness.** Validate synthetic and real ground-truth files across FAT32, TSK-backed filesystems, interrupted/cloned filesystems, fragmented files, already overwritten files, corrupt metadata, encrypted volumes and partial images. A byte-exact image smoke test alone does not demonstrate recovered deleted-file validity.

**P1: Package/distribution quality.** Signed native installers are unavailable; Python 3.10+ and optional PySide6/Tk prerequisites must be documented. Public policy embedded in an unmodified `.pyz` is not tamper-resistant and must not replace OS permissions. Run standard Gitea CI, including Rust tools and Xvfb, to completion and fix all new failures before a tagged beta.

**P2: Performance and Rust roadmap.** The optional Rust regular-file recovery core is retained. A full rewrite of UI, OS device discovery and journal paths into Rust is **not** justified without error/cancellation parity and measured real-workload wins. First benchmark sequential/sparse/USB/failing-drive I/O with per-model ceilings and fault injection; then migrate proven hot paths to Rust behind a testable interface. Neither this patch nor synthetic testing establishes superiority over SpinRite, DiskGenius or Acronis.

**P2: Static-finding hygiene.** The accompanying Repository Detective findings snapshot contains many `qtgui.py` Ruff E701/E702 formatting/style findings and potential missing-test flags. These are triage items, not independent proof of product safety or data corruption; mechanical full-file refactoring of a functioning GUI at the release boundary would add risk. Run Ruff and prioritize actual defects and missing tests; handle style cleanup in a separate reviewable commit. Some `GRAPH-ORPHAN-FILE` reports against `.gitignore`, `.gitattributes` and `LICENSE` are expected non-imported metadata, not dead code.

## How to integrate into Gitea safely

The patch was generated against the **uploaded snapshot**, *not* verified against a newer remote commit. If Gitea's `main` has changed since the archive, expect possible conflicts and review them manually.

```bash
# Recommended: apply the companion patch from the repo's root on the matching snapshot.
git switch -c remediation/driverepair-beta-hardening
git apply --check /path/to/DriveRepair_0.3.3b13_beta_hardening.patch
git apply /path/to/DriveRepair_0.3.3b13_beta_hardening.patch

cd desktop
python -m unittest discover -s tests -v
cd ..
python scripts/build_desktop.py --public-beta --no-wheel
python scripts/check_public_beta.py dist/DriveRepair-0.3.3b13-public-beta.pyz

# Review changes and CI before pushing.
git diff --check
git status --short
git add -A
git commit -m "Harden image-first beta recovery, safety checks, UI stop and docs"
git push -u origin remediation/driverepair-beta-hardening
```

The companion **source ZIP** contains a ready-to-review directory named `driverepair/`, including all changes. Use it instead of the patch if the source tree has no Git history. Do not overwrite a remote repository without reconciling its newer commits; do not commit the generated `dist/` directory as source. The optional `.pyz` is only a **testable candidate artifact** and is not a signed, hardware-qualified release.

For exact current-state documentation, read `README.md`, `CHANGELOG.md` → **Unreleased**, `docs/RELEASE_STATUS.md`, and `docs/PUBLIC_BETA_GATES.md`. Older engineering docs and `status.md` are retained as historical evidence, not claims of release qualification.
