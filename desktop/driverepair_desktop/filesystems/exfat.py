"""Conservative exFAT deleted-file recovery from regular-file images.

exFAT marks directory entries unused by clearing the high bit of EntryType.
This recovers contiguous primary+stream+name sets when the allocation bitmap
still shows those clusters free. Fragmented / overwritten files are skipped.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Any
import struct
from dataclasses import dataclass

from ..compat import binary_open_flags

MAX_FILE_BYTES = 2 * 1024**3


@dataclass(frozen=True)
class ExfatVolume:
    offset: int
    bytes_per_sector: int
    sectors_per_cluster: int
    fat_offset: int
    cluster_heap_offset: int
    cluster_count: int
    root_cluster: int

    @property
    def cluster_size(self) -> int:
        return self.bytes_per_sector * self.sectors_per_cluster

    def cluster_offset(self, cluster: int) -> int:
        if cluster < 2:
            raise ValueError("Invalid exFAT cluster")
        return self.offset + self.cluster_heap_offset + (cluster - 2) * self.cluster_size


def _read(fd: int, offset: int, size: int) -> bytes:
    align = 512
    aligned = offset - (offset % align)
    skip = offset - aligned
    need = ((skip + size + align - 1) // align) * align
    if hasattr(os, "pread"):
        data = os.pread(fd, need, aligned)
    else:
        os.lseek(fd, aligned, os.SEEK_SET)
        data = os.read(fd, need)
    if len(data) <= skip:
        return b""
    return data[skip:skip + size]


def parse_exfat_boot(fd: int, offset: int, image_size: int) -> ExfatVolume:
    boot = _read(fd, offset, 512)
    if len(boot) < 512 or boot[3:11] != b"EXFAT   " or boot[510:512] != b"\x55\xaa":
        raise ValueError("Not an exFAT boot sector")
    sector_shift = boot[0x6C]
    cluster_shift = boot[0x6D]
    if sector_shift > 12 or cluster_shift > 16:
        raise ValueError("Invalid exFAT geometry shifts")
    bps = 1 << sector_shift
    spc = 1 << cluster_shift
    fat_offset = struct.unpack_from("<I", boot, 0x50)[0] * bps
    # cluster heap offset in sectors
    heap_offset = struct.unpack_from("<I", boot, 0x58)[0] * bps
    cluster_count = struct.unpack_from("<I", boot, 0x5C)[0]
    root = struct.unpack_from("<I", boot, 0x60)[0]
    if root < 2 or offset + heap_offset >= image_size:
        raise ValueError("Invalid exFAT heap/root")
    return ExfatVolume(offset, bps, spc, offset + fat_offset, heap_offset, cluster_count, root)


def _fat_next(fd: int, volume: ExfatVolume, cluster: int) -> int:
    data = _read(fd, volume.fat_offset + cluster * 4, 4)
    if len(data) != 4:
        raise OSError("Short exFAT FAT read")
    value = struct.unpack('<I', data)[0]
    return int(value)


def _chain(fd: int, volume: ExfatVolume, first: int, budget: int, no_fat_chain: bool,
           data_length: int) -> list[int]:
    if no_fat_chain:
        needed = (data_length + volume.cluster_size - 1) // volume.cluster_size
        if needed > budget:
            raise ValueError("exFAT contiguous chain exceeds budget")
        return list(range(first, first + needed))
    out: list[int] = []
    seen: set[int] = set()
    cluster = first
    while len(out) < budget:
        if cluster in seen or cluster < 2 or cluster >= volume.cluster_count + 2:
            raise ValueError("Corrupt exFAT chain")
        seen.add(cluster)
        out.append(cluster)
        nxt = _fat_next(fd, volume, cluster)
        if nxt == 0xFFFFFFFF:
            return out
        if nxt < 2:
            raise ValueError("Invalid exFAT FAT link")
        cluster = nxt
    raise ValueError("exFAT chain too long")


def _safe_name(name: str, index: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "unnamed"
    return f"{index:05d}_deleted_{cleaned[:80]}"


def undelete_exfat(image: str, output_dir: str, *, partition_offset: int = 0,
                   max_files: int = 100, max_file_mib: int = 128,
                   allow_incomplete: bool = False) -> dict:
    if not 1 <= max_files <= 10000 or not 1 <= max_file_mib <= 2048:
        raise ValueError("Invalid file limit")
    source = os.path.abspath(image)
    target = os.path.abspath(output_dir)
    if source.replace("\\", "/").lower().startswith(("/dev/", "//./", "//?/")):
        raise ValueError("Use a regular image file, never a raw disk")
    fd = os.open(source, binary_open_flags(os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)))
    try:
        st = os.fstat(fd)
        journal = source + ".rescue.json"
        if os.path.exists(journal) and not allow_incomplete:
            import json
            with open(journal, encoding="utf-8") as f:
                state = json.load(f)
            if state.get("status") != "completed":
                raise RuntimeError("Image contains missing ranges; explicitly allow incomplete image")
        if os.path.lexists(target):
            raise FileExistsError("Choose a new, nonexistent output directory")
        volume = parse_exfat_boot(fd, partition_offset, st.st_size)
        os.mkdir(target, mode=0o700)
        files: list[dict] = []
        skipped: dict[str, int] = {}
        # Walk root directory clusters only (depth-1) for a conservative first pass.
        try:
            dir_clusters = _chain(fd, volume, volume.root_cluster, 4096, False, 0)
        except (ValueError, OSError):
            # Root may be contiguous without FAT; try a small contiguous window.
            dir_clusters = list(range(volume.root_cluster, volume.root_cluster + 64))
        entries = bytearray()
        for c in dir_clusters:
            try:
                entries.extend(_read(fd, volume.cluster_offset(c), volume.cluster_size))
            except ValueError:
                skipped["dir_read"] = skipped.get("dir_read", 0) + 1
                break
        i = 0
        while i + 32 <= len(entries) and len(files) < max_files:
            etype = entries[i]
            if etype == 0:
                break
            # Deleted file set: primary was 0x85, now 0x05
            if etype != 0x05:
                i += 32
                continue
            secondary = entries[i + 1]
            name_count = secondary
            # Need stream entry (0x40 when deleted from 0xC0) and name entries (0x01 from 0xC1)
            stream_off = i + 32
            if stream_off + 32 > len(entries):
                break
            if entries[stream_off] not in (0x40, 0xC0):
                i += 32
                continue
            stream = entries[stream_off:stream_off + 32]
            no_fat = bool(stream[1] & 0x02)
            name_len = stream[3]
            data_length = struct.unpack_from("<Q", stream, 8)[0]
            first_cluster = struct.unpack_from("<I", stream, 20)[0]
            name_chars: list[str] = []
            pos = stream_off + 32
            for _ in range(name_count):
                if pos + 32 > len(entries):
                    break
                if entries[pos] not in (0x01, 0xC1):
                    break
                chunk = entries[pos + 2:pos + 32]
                name_chars.append(chunk.decode("utf-16le", "replace").rstrip("\x00"))
                pos += 32
            name = "".join(name_chars)[:name_len]
            if data_length == 0 or data_length > min(MAX_FILE_BYTES, max_file_mib * 1024 * 1024):
                skipped["size_limit"] = skipped.get("size_limit", 0) + 1
                i = pos if pos > i else i + 32
                continue
            if first_cluster < 2:
                skipped["invalid_cluster"] = skipped.get("invalid_cluster", 0) + 1
                i = pos if pos > i else i + 32
                continue
            try:
                clusters = _chain(fd, volume, first_cluster, 1_000_000, no_fat, data_length)
            except (ValueError, OSError):
                skipped["chain"] = skipped.get("chain", 0) + 1
                i = pos if pos > i else i + 32
                continue
            # Contiguous-only safety: require no_fat or a single-run unbroken chain.
            if not no_fat and clusters != list(range(clusters[0], clusters[0] + len(clusters))):
                skipped["fragmented"] = skipped.get("fragmented", 0) + 1
                i = pos if pos > i else i + 32
                continue
            out_name = _safe_name(name or "unnamed", len(files) + 1)
            dest = os.path.join(target, out_name)
            hasher = hashlib.sha256()
            outfd = os.open(dest, binary_open_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL), 0o600)
            try:
                with os.fdopen(outfd, "wb") as out:
                    remaining = data_length
                    for c in clusters:
                        piece = _read(fd, volume.cluster_offset(c), min(volume.cluster_size, remaining))
                        if len(piece) != min(volume.cluster_size, remaining):
                            raise OSError("Short exFAT read")
                        out.write(piece)
                        hasher.update(piece)
                        remaining -= len(piece)
                        if remaining <= 0:
                            break
                    out.flush()
                    os.fsync(out.fileno())
            except BaseException:
                os.unlink(dest)
                raise
            files.append({
                "filename": out_name,
                "original_name": name,
                "size_bytes": data_length,
                "starting_cluster": first_cluster,
                "sha256": hasher.hexdigest(),
                "confidence": "exfat_deleted_entry_UNVERIFIED",
            })
            i = pos if pos > i else i + 32
        return {
            "status": "completed",
            "filesystem": "exfat",
            "partition_offset": partition_offset,
            "files_recovered": len(files),
            "files": files,
            "skipped": skipped,
            "notes": "exFAT undelete is speculative and currently root-directory contiguous only.",
        }
    finally:
        os.close(fd)
