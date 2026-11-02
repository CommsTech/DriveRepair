# DriveRepair — repair the original disk without an image (experimental)

> **Hardware release gate: NOT PASSED.** This workflow is intended for controlled
> experiments on expendable disks only until independent physical qualification.

## What the modes actually do

- **Quick repair:** a deterministic sample scan and nearby probes to identify
  slow/consistently readable regions, followed by journaled in-place rewrite,
  flush, and read-back verification of selected regions ONLY. Unscanned regions
  are unknown. A scan with no candidates performs **zero writes**.
- **Full repair:** reads the full surface and refreshes only selected slow,
  consistently readable regions. It does NOT rewrite every sector.
- **Full-surface refresh (advanced):** rewrites all *readable and stable* regions
  once, with verified readback; skips unreadable/inconsistent regions.
  This stresses the entire medium and may accelerate an already-failing disk.
- **Recovery/undelete:** distinct operations requiring a verified destination
  for reconstructed data. In-place media refresh is **not deleted-file rescue**,
  filesystem repair, ECC reconstruction, or reversal of physical wear.

## Temporary storage choices

| Journal | Data stored | Can restart after crash? | Platforms |
|---|---|---|---|
| Disk | Per-region preimage + metadata on separate healthy storage | Usually, subject to hardware integrity | Windows/Linux experimental |
| RAM disk | Per-region preimage + metadata in verified no-swap Linux tmpfs | If host RAM survived, potentially | Linux experimental |
| Process RAM only | Per-region preimage + metadata exclusively in process memory; **no image/journal files** | **NO** | Windows/Linux experimental |

Process RAM-only also has no persisted work log unless you choose to export
one. A UPS cannot prevent application crashes, USB bridge hangs, or disk
hardware failure. Windows pagefile/hibernation/OS policies are outside the
application's ability to guarantee that sensitive buffers never reach swap or
crash dumps; **zero journal files** does not guarantee zero incidental OS writes.

## Guided CLI example — Windows (privileged, offline patient only)

First run `driverepair-desktop list --json`; identify model, size, serial,
transport and `identity_hint`. Replace the values below. Use only on an
expendable patient. Do **NOT** guess a drive number.

```powershell
# The disk must NOT be mounted or used by Windows or another application.
driverepair-desktop care-external --device windows:PhysicalDriveN --mode quick `
  --journal-backend memory --ack-volatile-journal `
  --confirm-identity ABCDEF123456 --ack-risk --ack-destructive `
  --ack-no-backup --ack-data-loss-risk --ack-usb-bridge-risk `
  --ack-dock-power-backed `
  --ack-unvalidated-hardware --ack-unknown-health --json
```

`--ack-unknown-health` is optional, and should be omitted if accurate drive
health cannot be established safely. It does **not** bypass known health warnings.

For whole-surface maintenance use the GUI's In-place refresh tab, or
`refresh-external --mode full --journal-backend memory` with the same
acknowledgments and identity. It rewrites **readable** regions, not missing data.

## When to stop

If data is valuable, original media errors or serious SMART warnings are
present, the USB dock has unstable power, or a Windows filesystem is mounted,
**stop in-place work**. Preserve data using a separate destination or consult a
professional recovery service. Do not blindly override these limits.

A verified post-write match certifies only that newly written bytes match the
bytes obtained on the pre-write reads. There is no way to infer unknown
original bits or certify a physically worn drive as new from that comparison.
