# DriveRepair 0.3.3b18 — Statistical sector recovery (public-concept ladder)

Date: 2026-11-19.

## Scope and non-goals

- **Implemented from public maintenance concepts**, DriveRepair’s existing dual-read rules, and industry practice (multi-sample reads, settle delays, levelled intensity).
- **Not** a reverse-engineered copy of `SPINRITE.EXE`, Flux Synthesizer pattern generators, or proprietary DynaStat code. The local `H:\SpinRite.iso` was listed only; the proprietary binary was **not** decompiled.
- **Not** a claim of magnetic wear reversal, bit-perfect historical reconstruction, or lifetime extension certificates.
- SSD / flash / unknown-USB **write gates from 0.3.3b16/b17 remain authoritative**.

## What improved relative to prior DriveRepair + classic dual-read

| Capability | Before | 0.3.3b18 |
|---|---|---|
| Consistency | N identical reads, mismatch → skip | Same baseline, plus settle delays |
| Marginal sectors | Skip on any disagreement | Optional high-confidence **sector majority** (levels 4–5 only) |
| Intensity | Mode/policy only | Explicit maintenance levels 1–5 |
| Investigation | Dual-read bisect | Sector-size statistical second chance (still fail-closed) |
| Postverify | Two reads | Optional settle + 2–3 samples on deep/extreme |

Fail-closed rule: below the configured agreement threshold, bytes are **never invented**.

## Maintenance levels

| Level | Name | Samples | Settle | Sector majority |
|---|---|---|---|---|
| 1 | quick | 2 | 0 ms | no |
| 2 | normal (GUI default) | 3 | 5 ms | no |
| 3 | thorough | 5 | 15 ms | no |
| 4 | deep | 8 | 25 ms | ≥75% |
| 5 | extreme | 15 | 40 ms | ≥80% |

CLI: `--maintenance-level 1|2|3|4|5|quick|normal|thorough|deep|extreme` on `refresh-*` and `care-*`.

## Hardware QA still required

Sacrificial rotational HDD only. Confirm SSD/unknown USB still cannot start authorized repair. Record level, samples, method (`unanimous` vs `sector_majority`), agreement ratio, and whether any patient write occurred.
