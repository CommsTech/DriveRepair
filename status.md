# Status — 2026-11-01

PRIVATE TEST — Seagate ST1000LM048 1TB USB lab **complete** on 0.3.3b1 + Windows sparse/O_BINARY fixes.

## Merged follow-ups
| PR | Fix |
|----|-----|
| #89 | Sparse SetEndOfFile (no zero-fill) |
| (pending this) | Integrity restore O_BINARY + lab prefix workflow |

## Seagate results (`138b614ad5ea`)
| Step | Result |
|------|--------|
| triage/sample | 0 errors |
| benchmark | ~65 MiB/s |
| bounded rescue | **32 MiB / 32 chunks in ~19.5s**; sparse logical 1TB; VDL=32MiB |
| detect (prefix) | no known FS in first 32MiB |
| integrity | 1 flipped chunk detected → restore → **byte-exact** |

Lab: `D:\DriveRepairLab\seagate_st1000lm048_1tb_20261101_151108\`
