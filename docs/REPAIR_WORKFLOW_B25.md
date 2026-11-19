# DriveRepair b25 — Repair & Restore qualification

## Changed UX

- Choose the selected drive before entering Repair & restore.
- On SanDisk SDSSDH3, the primary action must say **Recover SSD data** and switch to read-only image rescue, never launch `care-external`.
- On a Seagate ST1000LM048 with no usable SMART/native evidence, the primary action must be **Identify disk (read-only)** or **Create a recovery image**, never falsely enable the writer.
- On a synthetic/full SMART-qualified rotational HDD, **Review guarded HDD repair** is allowed by UI but engine must still independently revalidate device, journal, health, locks and explicit acknowledgements.
- **Repair a recovered filesystem copy…** opens the specialist dialog with `repair-ext-image` preselected. The operation only supports ext2/3/4 *volume* images and writes to a new copy. It does not provide an NTFS or exFAT repair.

## Hardware tests still required

1. Native Windows PySide6 clickthrough at 100%, 125% and 150% DPI, including keyboard navigation and narrow windows.
2. Identify a known-good sacrificial Seagate SATA HDD both directly and behind each candidate USB bridge. Capture SMART/SAT response and Windows-native flags; do not infer drive health from the model name.
3. After data backup, on a **disposable HDD** test journal location, unique serial, volume lock, interrupted I/O, bounded rewrite and independent post-write readback; preserve all failure evidence.
4. Test read-only imaging from SanDisk SSD and generic USB flash to separate healthy storage. Confirm no patient writes and inspect journal/recovered-byte map.
5. Verify no SSD, flash, unknown, or model/serial-mismatch device can start magnetic HDD rewrite even via CLI.
6. Exercise copy-only ext filesystem repair on a deliberately damaged synthetic ext filesystem image and assert original digest is unchanged. NTFS and exFAT need dedicated verified workflows.

A synthetic test pass does **not** demonstrate repaired media health or native Windows device support.
