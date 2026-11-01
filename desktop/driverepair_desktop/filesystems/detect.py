"""Conservative on-disk filesystem / partition detection for recovery routing."""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass

from ..compat import binary_open_flags

SECTOR = 512


@dataclass(frozen=True)
class DetectedFilesystem:
    kind: str
    offset: int
    size_hint: int | None
    confidence: str
    notes: str = ""


def _read(fd: int, offset: int, size: int) -> bytes:
    align = 512
    aligned = offset - (offset % align)
    skip = offset - aligned
    need = ((skip + size + align - 1) // align) * align
    if hasattr(os, "pread") and os.name != "nt":
        data = os.pread(fd, need, aligned)
    else:
        if hasattr(os, "pread"):
            data = os.pread(fd, need, aligned)
        else:
            os.lseek(fd, aligned, os.SEEK_SET)
            data = os.read(fd, need)
    if len(data) <= skip:
        return b""
    return data[skip:skip + size]


def _classify_superblock(sector: bytes, offset: int, size_hint: int | None) -> DetectedFilesystem | None:
    if len(sector) < 512:
        return None
    # NTFS
    if sector[3:11] == b"NTFS    " and sector[510:512] == b"\x55\xaa":
        return DetectedFilesystem("ntfs", offset, size_hint, "boot_oem_ntfs")
    # exFAT
    if sector[3:11] == b"EXFAT   " and sector[510:512] == b"\x55\xaa":
        return DetectedFilesystem("exfat", offset, size_hint, "boot_oem_exfat")
    # FAT32 (with FAT32 signature field or typical layout)
    if sector[510:512] == b"\x55\xaa":
        fat32_sig = sector[82:90]
        fs_type = sector[54:62]
        if fat32_sig.startswith(b"FAT32") or fs_type.startswith(b"FAT32"):
            return DetectedFilesystem("fat32", offset, size_hint, "boot_fat32")
        if fs_type.startswith(b"FAT16") or fs_type.startswith(b"FAT12"):
            return DetectedFilesystem("fat16", offset, size_hint, "boot_fat16_limited")
    # ext2/3/4 superblock lives at +1024; caller may pass that block as sector-like.
    if len(sector) >= 0x3C + 2 and sector[0x38:0x3C] == b"\x53\xef":
        return DetectedFilesystem("ext", offset, size_hint, "ext_magic")
    # Btrfs: magic at offset 64 within superblock (which is at 64KiB on device)
    if b"_BHRfS_M" in sector[:128]:
        return DetectedFilesystem("btrfs", offset, size_hint, "btrfs_magic")
    # ZFS: uberblock magic 0x00bab10c (little-endian) appears in labels
    if b"\x0c\xb1\xba\x00" in sector[:256] or sector[:4] == b"\x0c\xb1\xba\x00":
        return DetectedFilesystem("zfs", offset, size_hint, "zfs_uber_magic_weak")
    # APFS container
    if sector[32:36] == b"NXSB":
        return DetectedFilesystem("apfs", offset, size_hint, "apfs_nxsb")
    return None


def _mbr_partitions(mbr: bytes) -> list[tuple[int, int, int]]:
    """Return (status_type_byte, lba, sectors) for occupied MBR slots."""
    out: list[tuple[int, int, int]] = []
    if len(mbr) < 512 or mbr[510:512] != b"\x55\xaa":
        return out
    for i in range(4):
        entry = mbr[446 + i * 16:462 + i * 16]
        ptype = entry[4]
        if ptype == 0:
            continue
        lba, sectors = struct.unpack_from("<II", entry, 8)
        if lba and sectors:
            out.append((ptype, lba, sectors))
    return out


def detect_filesystems(image: str) -> list[DetectedFilesystem]:
    """Detect filesystems on a regular-file disk/volume image (read-only)."""
    path = os.path.abspath(image)
    if path.replace("\\", "/").lower().startswith(("/dev/", "//./", "//?/")):
        raise ValueError("detect_filesystems requires a regular image file, not a raw device")
    fd = os.open(path, binary_open_flags(os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)))
    try:
        size = os.fstat(fd).st_size
        found: list[DetectedFilesystem] = []
        seen: set[tuple[str, int]] = set()

        def add(item: DetectedFilesystem | None) -> None:
            if not item:
                return
            key = (item.kind, item.offset)
            if key in seen:
                return
            seen.add(key)
            found.append(item)

        # Whole-image / volume boot sector
        add(_classify_superblock(_read(fd, 0, 512), 0, size))
        # ext superblock
        add(_classify_superblock(_read(fd, 1024, 256), 0, size))
        # Btrfs primary superblock at 64 KiB
        add(_classify_superblock(_read(fd, 65536, 128), 0, size))
        # APFS / ZFS probes near start
        add(_classify_superblock(_read(fd, 0, 512), 0, size))

        mbr = _read(fd, 0, 512)
        for ptype, lba, sectors in _mbr_partitions(mbr):
            off = lba * SECTOR
            if off >= size:
                continue
            hint = sectors * SECTOR
            add(_classify_superblock(_read(fd, off, 512), off, hint))
            add(_classify_superblock(_read(fd, off + 1024, 256), off, hint))
            if off + 65536 < size:
                add(_classify_superblock(_read(fd, off + 65536, 128), off, hint))

        # GPT basic: look for EFI PART at LBA1 and first few partition entries
        gpt_hdr = _read(fd, SECTOR, 92)
        if gpt_hdr[:8] == b"EFI PART":
            part_lba = struct.unpack_from("<Q", gpt_hdr, 72)[0]
            entry_size = struct.unpack_from("<I", gpt_hdr, 84)[0] or 128
            num = min(struct.unpack_from("<I", gpt_hdr, 80)[0], 128)
            table = _read(fd, part_lba * SECTOR, num * entry_size)
            for i in range(num):
                entry = table[i * entry_size:(i + 1) * entry_size]
                if len(entry) < 56 or entry[:16] == b"\x00" * 16:
                    continue
                first_lba, last_lba = struct.unpack_from("<QQ", entry, 32)
                off = first_lba * SECTOR
                hint = (last_lba - first_lba + 1) * SECTOR
                if off < size:
                    add(_classify_superblock(_read(fd, off, 512), off, hint))

        if not found:
            found.append(DetectedFilesystem(
                "unknown", 0, size, "no_known_superblock",
                "No FAT/NTFS/exFAT/ext/Btrfs/ZFS/APFS signature recognized; RAW carve only.",
            ))
        return found
    finally:
        os.close(fd)
