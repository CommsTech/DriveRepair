# BitLocker / encryption-aware recovery

Windows devices are often BitLocker-encrypted by default. DriveRepair must treat
that as a first-class case — not as “a broken NTFS volume.”

## What BitLocker looks like on disk

- Volume boot record OEM name: `-FVE-FS-`
- Payload sectors are **ciphertext** (high entropy). JPEG/PNG signatures found
  inside are almost always false positives.

## Safe vs unsafe workflows

| Goal | Safe approach | Unsafe approach |
|---|---|---|
| Keep the encrypted volume intact | Raw image the disk, or byte-identical Adaptive/Full refresh | Carve/undelete/repair the locked volume |
| Get user files back | Unlock with recovery key / protector, then copy from plaintext | Treat ciphertext as damaged files |
| Restore to a replacement disk | Restore the **full raw image** (ciphertext), then unlock on the new hardware | Format + copy carved junk |

## Commands

```text
driverepair inspect-encryption --image PATH --json
```

File-oriented commands (`carve-image`, `undelete-fat32`, `check-ext-image`,
`repair-ext-image`) **fail closed** when BitLocker/LUKS signatures are found.
Override only with `--ack-encrypted-volume` after you understand results will
be meaningless noise.

In-place media refresh **may** run on encrypted media because it rewrites the
same bytes it just read — it does not decrypt or reinterpret filesystem
structures. The CLI prints a warning when signatures are visible on file images.

## Operator checklist (BitLocker patient)

1. Prefer raw rescue/image to healthy storage.
2. Do not carve the locked image.
3. Unlock with the 48-digit BitLocker recovery key (or TPM/password protector).
4. Only then run file recovery / undelete on the unlocked volume or a decrypted copy.
5. If the disk is dying, prioritize imaging + key escrow over filesystem tricks.
