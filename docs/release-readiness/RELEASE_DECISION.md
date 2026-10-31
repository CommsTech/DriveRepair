# Release decision

**Date:** 2026-10-31  
**Commit baseline:** `main` after public-docs packaging  

## Decision

| Question | Answer |
|---|---|
| May this repository be published publicly? | **Yes**, as an **experimental open-source** project |
| May it be marketed as a disk **repair** utility? | **No** |
| May it be marketed as a read-only external disk **surface scanner**? | **Yes**, with limitations clearly stated |
| Production BIOS/UEFI repair USB | **No** — experimental / disabled |
| Competitive “better than X” claims | **Forbidden** until controlled lab evidence exists |

## Allowed public claims

- Cross-platform desktop CLI for listing and read-only scanning of external whole disks
- Does not write to the scanned source disk
- Synthetic unit tests exist and should be run before trusting local builds
- MIT licensed

## Forbidden public claims

- Repairs bad sectors / remaps media / recovers unreadable data
- Replaces commercial repair suites
- Verified SMART health from empty or stubbed backends
- Bootable USB “fixes your drive”

## Operator warnings (must ship in README)

- Full scans can stress failing media — image first
- Successful reads are not integrity proofs
- Privileges and USB bridges vary by OS
