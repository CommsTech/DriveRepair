# In-Place Media Refresh

Dedicated destructive mode **alongside** image-based recovery. It does not replace rescue/imaging and is **not** equivalent to having a backup.

## Rolling journal

Active region state machine:

`SAVED → WRITING → VERIFIED → COMMITTED`

1. Read region with ≥2 identical consistency reads.
2. Persist original bytes to `region.bin` and mark `SAVED`.
3. Mark `WRITING`, rewrite in place, flush.
4. Optional verify read → `VERIFIED`.
5. Advance and clear blob → `COMMITTED`.

On restart, an interrupted `SAVED`/`WRITING` region is restored from the journal (or flagged if the blob is missing/corrupt) before new work continues.

## Modes

| Mode | Behavior |
|---|---|
| `adaptive` (default) | Probe latency; refresh unusually slow but consistently readable regions |
| `full` | Sequential whole-surface refresh (high risk; long on multi-TB USB) |

Unreadable or inconsistent sectors are **never** auto-rewritten.

## Live hardware gate

External refresh requires `--ack-unvalidated-hardware` until sacrificial HDD tests (forced interrupt + USB disconnect) pass. The 12 TB patient should wait for that validation.
