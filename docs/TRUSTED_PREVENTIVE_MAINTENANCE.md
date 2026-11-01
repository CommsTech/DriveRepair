# When to refresh media, when to rescue, and how to earn user trust

**Trust is measured in preserved bytes, not in the number of rewrite passes.**

## Three different operations

1. **Data rescue (source read-only)**: save the best available bytes to separate
   media and keep a durable map of unrecovered ranges. This is the first response
   to symptoms of active drive failure.
2. **Filesystem integrity repair**: work from redundancy, known checksums or a
   verified clone. Fixing metadata is not physical head/platter repair and can
   discard otherwise recoverable file references.
3. **Media maintenance**: selected rewrites of consistently readable content
   may refresh magnetic recording, or cause HDD firmware to reassess/remap
   sectors. NAND firmware may perform internal refresh/retention management.
   These do not reverse worn-out magnetic heads, scratched platters, depleted
   NAND endurance, or a failing USB bridge.

## Safe automatic monitoring, not automatic writes

Scheduled SMART/NVMe history and bounded read-only samples can identify
worsening signals. Nonzero baseline HDD SMART 5/187/197/198 or NVMe media errors
are **actionable on their first reading**, even when overall SMART says PASSED.
A worsening reading triggers: warning → preserve important data → verify current
backup or clone → investigate USB power/cable/bridge and device health.

Unlike a filesystem with **known-good redundant blocks and checksums**, DriveRepair
cannot infer the true contents of a silently corrupted sector from an ordinary
successful read. Automatic rewriting may overwrite the last salvageable copy,
turn correctable problems into permanent ones, or consume an unstable drive's
remaining service life. USB errors are frequently transport-related; refreshing
sectors will not repair a marginal cable or dock. A UPS does not prevent USB
resets, OS crashes or hardware death. A rolling journal protects only the
current rewrite region; it is not a backup.

**A future trusted autonomous maintenance mode** needs ALL of: independent,
verified backup/redundancy, correct original-block checksum or equivalent data
proof, identity and lock validation immediately before writing, drive-class-aware
policy, exact persistent transaction journal on a separate failure domain,
forced-failure tests, explicit per-device opt-in, cooling/load limits, rollback
where possible, and report of pre-/post-state. Failing/unknown conditions should
prefer replacement or manual expert recovery.

## Reproducible before/after measurements

- Identify model/firmware/capacity/media type/interface and USB bridge.
- Capture SMART/NVMe counters before/after, with missing telemetry as UNKNOWN.
- Record location and latency of slow/unreadable blocks, repeat count,
  temperatures, throughput, total source reads/writes, and reset count.
- Record hashes of all known recovered bytes and exact source/output integrity
  on stable reference samples. A 100% successful host read is **not** proof
  of original bit correctness without a trusted checksum/reference.
- Assess whether latency improvement persists after power-cycle and multiple
  clean rereads; otherwise label it unproven.
- Compare recovery to GNU ddrescue and OpenSuperClone on comparable initial
  media conditions, never sequentially on one continuously deteriorating disk.

For ZFS, use the filesystem's own scrub and repair from redundancy where
possible. ZFS protects data using checksums and can repair from redundant copies;
blind in-place host writes are not a substitute.

References: GNU ddrescue manual (2026), NIST SP 800-88r2 (2025), OpenZFS
Scrub/Resilver documentation, Google FAST 2007 large-fleet failure study,
manufacturer SSD retention/read-disturb documentation. See `BENCHMARK_PROTOCOL.md`.
