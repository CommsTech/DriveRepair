# DriveRepair architecture — 0.3.1b1

**Status:** Partial Rust migration. Do NOT describe the Python desktop core as fully migrated.

```text
                  Desktop GUI (Tk) / CLI (Python)
                       |       |       |
   read-only inventory |       |       +-- optional local tools:
   and SMART/health    |       |           smartctl, e2fsck, fls, icat
                       |       |
            image & file tools   +-- guided workflows, private JSON
                       |           history and forensic SHA-256 reports
                       |
             optional Rust recovery-core binary
            (regular image files, never raw disks)
                       |
           forward copy / reverse split retry
                 + .rmap checkpoint sidecar

     Original src/boot/bios + src/boot/uefi retained:
     experimental only; not a validated bootable rescue image.
```

## Contract boundaries

1. No source mutations in a rescue/undelete/forensic operation. Output files are always NEW paths and never devices.
2. A regular-file recovery engine may not be silently substituted for a physical-device recovery engine.
3. Python image rescue (`.rescue.json`) and Rust image rescue (`.rmap`) use DIFFERENT journal formats; never cross-resume.
4. Incomplete reads are unverified gaps. The output bytes do NOT certify data correctness.
5. Low-level raw media refresh is separate and explicitly gated by device identity, idle status and a rollback journal; do not reuse for read-only operations.
6. Device selection is through stable fingerprint + human model, size, bus/location and masked serial; short fingerprints are not cryptographic proof of authenticity.
7. Case reports redact paths by default and never upload data to a service.

## Migration stages

- **Stage 1, current:** small no-dependency Rust regular-image rescue, existing Python UI/CLI and filesystem tooling; cross-platform Cargo CI; no direct raw writes from Rust.
- **Stage 2:** prove Rust engine equivalence on fault injection, interrupted output, map corruption, large images and byte-accurate comparisons on all OSes. Promote Rust image rescue only after repeatable tests. Add documented, versioned machine-readable progress.
- **Stage 3:** properly isolated platform raw-I/O adapters with handles bound to stable IDs, documented volume locks and provenance. This should be a separately reviewed change, not an extension of file-only code by swapping paths.
- **Stage 4:** native GUI packaging/installer/signing and independently tested bootable live environment. Prefer a maintained OS's storage drivers, not custom controller/firmware access when standard APIs suffice.

## Technical caution

Moving CPU and memory-bound tasks into Rust can reduce overhead. On a seriously failing HDD, the bottleneck is often disk firmware retries, bad-head mechanics, USB bridge resets or thermal events, not Python execution. Measure throughput, recovered verified bytes, tail latency, read amplification, memory, and source writes under identical conditions. Do not claim superiority from a clean synthetic image.

## Experimental live recovery architecture (0.3.1b1)

A Debian live-build recipe packages the **Python desktop client and its
existing optional local forensic tools** into an x86-64 live ISO target.
The live OS uses Linux kernel drivers; the legacy bare-metal Rust BIOS/UEFI
crates remain unsupported. No ISO boot test has been performed in this sandbox.
The non-destructive offline `rescue-system` path is separate from ordinary
external-only scanning and checks source idle state, identity, and destination
ancestry/network mount before opening a read-only device handle.
