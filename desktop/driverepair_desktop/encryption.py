"""Detect full-disk / volume encryption so recovery does not mis-handle ciphertext.

BitLocker (and similar) volumes store ciphertext on disk. Signature carving,
FAT undelete, and filesystem "repair" against locked ciphertext produce garbage
that looks like broken files and can waste operator time — or worse, encourage
destructive fixes on encrypted metadata.

Safe paths for BitLocker patients:
  1. Raw sector imaging / byte-identical in-place refresh (preserves ciphertext).
  2. Unlock with the recovery key / TPM protector, THEN recover files from the
     plaintext filesystem (or from an unlocked Virtual Disk / mounted volume).
  3. Never carve or "repair" a locked BitLocker volume as if it were NTFS/FAT.
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass


# BitLocker volume boot sector OEM / FS name field (offset 3, 8 bytes).
BITLOCKER_OEM = b"-FVE-FS-"
# Older / related Microsoft FVE markers occasionally seen near VBR.
BITLOCKER_HINTS = (b"-FVE-FS-", b"FVE-FS", b"BitLocker")
LUKS_MAGIC = b"LUKS\xba\xbe"


@dataclass(frozen=True)
class EncryptionFinding:
    kind: str              # bitlocker | luks | unknown_encrypted_hint
    offset: int
    detail: str
    confidence: str        # high | medium | low

    def public(self) -> dict:
        return {
            "kind": self.kind,
            "offset": self.offset,
            "detail": self.detail,
            "confidence": self.confidence,
        }


def _read_at(path: str, offset: int, count: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        if hasattr(os, "pread"):
            return os.pread(fd, count, offset)
        os.lseek(fd, offset, os.SEEK_SET)
        return os.read(fd, count)
    finally:
        os.close(fd)


def _gpt_partition_starts(path: str, sector: int = 512, limit: int = 128) -> list[int]:
    """Return byte offsets of GPT partition entries (best-effort; empty on MBR-only)."""
    header = _read_at(path, sector, sector)
    if len(header) < 92 or header[0:8] != b"EFI PART":
        return []
    part_lba = struct.unpack_from("<Q", header, 72)[0]
    entry_size = struct.unpack_from("<I", header, 84)[0]
    part_count = struct.unpack_from("<I", header, 80)[0]
    if entry_size < 128 or part_count <= 0:
        return []
    part_count = min(part_count, limit)
    table = _read_at(path, part_lba * sector, part_count * entry_size)
    starts: list[int] = []
    for i in range(part_count):
        entry = table[i * entry_size:(i + 1) * entry_size]
        if len(entry) < 40 or entry[0:16] == b"\x00" * 16:
            continue
        first_lba = struct.unpack_from("<Q", entry, 32)[0]
        if first_lba:
            starts.append(first_lba * sector)
    return starts


def inspect_boot_sector(data: bytes, offset: int = 0) -> EncryptionFinding | None:
    if len(data) < 16:
        return None
    oem = data[3:11]
    if oem == BITLOCKER_OEM or data[3:10] == b"FVE-FS\x00":
        return EncryptionFinding(
            "bitlocker", offset,
            "BitLocker volume boot record (-FVE-FS-)",
            "high",
        )
    if data.startswith(LUKS_MAGIC):
        return EncryptionFinding(
            "luks", offset,
            "LUKS encrypted container header",
            "high",
        )
    # Low-confidence hint scan in the first sector only.
    head = data[: min(512, len(data))]
    for hint in BITLOCKER_HINTS:
        if hint in head and oem != b"NTFS    ":
            return EncryptionFinding(
                "bitlocker", offset,
                f"BitLocker-related marker {hint!r} near sector start",
                "medium",
            )
    return None


def scan_path_for_encryption(path: str, *, max_partitions: int = 16) -> list[EncryptionFinding]:
    """Scan image/device path for BitLocker/LUKS signatures (read-only)."""
    findings: list[EncryptionFinding] = []
    try:
        size = os.path.getsize(path)
    except OSError:
        size = -1

    # Protective / hybrid MBR area + common first-partition guesses.
    candidates = [0, 512, 1024 * 1024, 2048 * 512]
    try:
        candidates.extend(_gpt_partition_starts(path)[:max_partitions])
    except OSError:
        pass

    seen: set[int] = set()
    for offset in candidates:
        if offset in seen:
            continue
        seen.add(offset)
        if size >= 0 and offset >= size:
            continue
        try:
            data = _read_at(path, offset, 512)
        except OSError:
            continue
        hit = inspect_boot_sector(data, offset)
        if hit is not None:
            findings.append(hit)
    return findings


def require_plaintext_filesystem(
    path: str,
    *,
    ack_encrypted_volume: bool = False,
    operation: str = "filesystem recovery",
) -> list[EncryptionFinding]:
    """Fail closed when BitLocker/LUKS is detected unless explicitly acknowledged.

    Acknowledgement only bypasses the hard stop for operators who already unlocked
    a copy or accept that results will be meaningless ciphertext noise — it does
    NOT decrypt anything.
    """
    findings = scan_path_for_encryption(path)
    serious = [f for f in findings if f.confidence in {"high", "medium"}]
    if not serious:
        return findings
    if ack_encrypted_volume:
        return findings
    kinds = ", ".join(sorted({f.kind for f in serious}))
    offsets = ", ".join(str(f.offset) for f in serious[:4])
    raise ValueError(
        f"Refusing {operation}: detected {kinds} at byte offset(s) {offsets}. "
        "Locked ciphertext is not a damaged NTFS/FAT filesystem — carving or "
        "undelete here invents garbage files and can mislead restore decisions. "
        "Image the raw disk (or run byte-identical media refresh), unlock with "
        "the BitLocker recovery key / protector, then recover from plaintext. "
        "To override after you understand this, pass --ack-encrypted-volume."
    )


def encryption_guidance(findings: list[EncryptionFinding]) -> list[str]:
    if not findings:
        return []
    notes = [
        "Encrypted volume signatures were detected. Prefer raw imaging over file carving.",
        "BitLocker restore path: preserve ciphertext → unlock with recovery key → then copy files.",
        "Do not run filesystem repair tools against a locked BitLocker volume.",
    ]
    if any(f.kind == "bitlocker" for f in findings):
        notes.append(
            "Windows: manage-bde / unlock-BitLocker with the 48-digit recovery key "
            "after the volume is imaged or the disk is healthy enough to mount."
        )
    return notes
