# Filesystem & RAW recovery (0.2.9b1+)

## Commands

```bash
python -m driverepair_desktop detect-filesystems --image disk.img --json
python -m driverepair_desktop recover-image --image disk.img --output-dir recovered --mode auto --json
python -m driverepair_desktop recover-image --image disk.img --output-dir recovered_fs --mode filesystem --json
python -m driverepair_desktop recover-image --image disk.img --output-dir recovered_raw --mode raw --formats pdf mp4 ole docx --json
```

Always work from a **regular-file image** of the patient (never write recovered files back onto the source device).

## Mode matrix

| Detected FS | `filesystem` undelete | `raw` carve | `auto` |
|---|---|---|---|
| FAT32 | Yes (contiguous) | Yes | Both |
| NTFS | Yes (deleted MFT, best-effort) | Yes | Both |
| exFAT | Yes (root contiguous, best-effort) | Yes | Both |
| ext2/3/4 | No (use `check-ext-image` / clone repair) | Yes | RAW + note |
| Btrfs / ZFS / APFS | No | Yes | RAW + note |
| Unknown | No | Yes | RAW |

## Honesty limits

- Every undeleted/carved file is **UNVERIFIED**.
- Fragmented, overwritten, encrypted (BitLocker/FileVault/LUKS), and deduplicated objects are out of scope for this pass.
- Plain `.txt` is recovered by **filesystem undelete** when directory metadata survives — not by RAW carving.
- Btrfs/ZFS/APFS undelete remains future work; detection exists so `auto` fails open to RAW instead of claiming false FS recovery.
