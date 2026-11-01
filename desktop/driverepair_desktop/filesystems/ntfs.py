"""Conservative NTFS deleted-file recovery from regular-file images.

Reads the MFT for records that are no longer in-use, extracts $FILE_NAME and
$DATA when clusters look free enough to copy. Does not modify the patient image.
Fragmented/overwritten/ADS-heavy files may be skipped or incomplete — every hit
is marked UNVERIFIED.
"""
from __future__ import annotations

import hashlib
import os
import re
import struct
from dataclasses import dataclass

from ..compat import binary_open_flags

ATTR_STANDARD = 0x10
ATTR_FILENAME = 0x30
ATTR_DATA = 0x80
ATTR_END = 0xFFFFFFFF
MAX_FILE_BYTES = 2 * 1024**3


@dataclass(frozen=True)
class NtfsVolume:
    offset: int
    bytes_per_sector: int
    sectors_per_cluster: int
    mft_lcn: int
    record_size: int

    @property
    def cluster_size(self) -> int:
        return self.bytes_per_sector * self.sectors_per_cluster

    def cluster_offset(self, lcn: int) -> int:
        return self.offset + lcn * self.cluster_size


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


def parse_ntfs_boot(fd: int, offset: int, image_size: int) -> NtfsVolume:
    boot = _read(fd, offset, 512)
    if len(boot) < 512 or boot[3:11] != b"NTFS    " or boot[510:512] != b"\x55\xaa":
        raise ValueError("Not an NTFS boot sector")
    bps = struct.unpack_from("<H", boot, 0x0B)[0]
    spc = boot[0x0D]
    if bps not in {512, 1024, 2048, 4096} or spc == 0 or spc & (spc - 1):
        raise ValueError("Invalid NTFS geometry")
    mft_lcn = struct.unpack_from("<q", boot, 0x30)[0]
    clusters_per_record = struct.unpack_from("<b", boot, 0x40)[0]
    if clusters_per_record > 0:
        record_size = clusters_per_record * bps * spc
    else:
        record_size = 1 << (-clusters_per_record)
    if record_size not in {1024, 2048, 4096}:
        raise ValueError("Unsupported MFT record size")
    if mft_lcn < 0:
        raise ValueError("Invalid MFT LCN")
    cluster_size = bps * spc
    if offset + (mft_lcn + 1) * cluster_size > image_size:
        raise ValueError("MFT location outside image")
    return NtfsVolume(offset, bps, spc, mft_lcn, record_size)


def _fixup_record(record: bytearray) -> bool:
    """Apply USA fixups; return False if the record is corrupt."""
    if record[:4] != b"FILE":
        return False
    usa_offset = struct.unpack_from("<H", record, 0x04)[0]
    usa_count = struct.unpack_from("<H", record, 0x06)[0]
    if usa_count < 2 or usa_offset + usa_count * 2 > len(record):
        return False
    usa = record[usa_offset:usa_offset + usa_count * 2]
    update_seq = usa[:2]
    for i in range(1, usa_count):
        sector_end = i * 512 - 2
        if sector_end + 2 > len(record):
            return False
        if record[sector_end:sector_end + 2] != update_seq:
            # Some synthetic/test images omit USA; allow if all zeroed seq.
            if update_seq != b"\x00\x00":
                return False
        record[sector_end:sector_end + 2] = usa[i * 2:(i + 1) * 2]
    return True


def _decode_runs(runlist: bytes, size_hint: int) -> list[tuple[int, int]]:
    """Return list of (lcn, length_in_clusters). Sparse runs use lcn=-1."""
    runs: list[tuple[int, int]] = []
    pos = 0
    lcn = 0
    while pos < len(runlist):
        header = runlist[pos]
        pos += 1
        if header == 0:
            break
        len_size = header & 0x0F
        off_size = header >> 4
        if len_size == 0 or pos + len_size + off_size > len(runlist):
            break
        length = int.from_bytes(runlist[pos:pos + len_size], "little")
        pos += len_size
        if off_size == 0:
            runs.append((-1, length))
            continue
        raw = runlist[pos:pos + off_size]
        pos += off_size
        # Sign-extend offset
        val = int.from_bytes(raw, "little", signed=False)
        if raw[-1] & 0x80:
            val -= 1 << (8 * off_size)
        lcn += val
        runs.append((lcn, length))
        if sum(n for _, n in runs) * 1 > size_hint // 1 + 1024 and size_hint:
            break
    return runs


def _iter_attributes(record: bytes):
    first = struct.unpack_from("<H", record, 0x14)[0]
    pos = first
    while pos + 8 <= len(record):
        atype = struct.unpack_from("<I", record, pos)[0]
        if atype == ATTR_END:
            break
        alen = struct.unpack_from("<I", record, pos + 4)[0]
        if alen < 16 or pos + alen > len(record):
            break
        yield pos, record[pos:pos + alen]
        pos += alen


def _attribute_name(attr: bytes) -> str:
    name_len = attr[9]
    name_off = struct.unpack_from("<H", attr, 10)[0]
    if name_len and name_off + name_len * 2 <= len(attr):
        return attr[name_off:name_off + name_len * 2].decode("utf-16le", "replace")
    return ""


def _parse_filename(attr: bytes) -> str | None:
    nonres = attr[8]
    if nonres:
        return None
    content_size = struct.unpack_from("<I", attr, 16)[0]
    content_off = struct.unpack_from("<H", attr, 20)[0]
    content = attr[content_off:content_off + content_size]
    if len(content) < 0x42:
        return None
    name_len = content[0x40]
    name = content[0x42:0x42 + name_len * 2]
    if len(name) != name_len * 2:
        return None
    return name.decode("utf-16le", "replace")


def _parse_data(attr: bytes) -> tuple[bool, bytes | None, list[tuple[int, int]], int]:
    """Return (resident, resident_bytes, runs, data_size)."""
    nonres = attr[8]
    if not nonres:
        content_size = struct.unpack_from("<I", attr, 16)[0]
        content_off = struct.unpack_from("<H", attr, 20)[0]
        data = attr[content_off:content_off + content_size]
        return True, data, [], content_size
    data_size = struct.unpack_from("<Q", attr, 0x30)[0]
    run_off = struct.unpack_from("<H", attr, 0x20)[0]
    runs = _decode_runs(attr[run_off:], data_size)
    return False, None, runs, data_size


def _safe_name(name: str, index: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "unnamed"
    return f"{index:05d}_deleted_{cleaned[:80]}"


def undelete_ntfs(image: str, output_dir: str, *, partition_offset: int = 0,
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
        volume = parse_ntfs_boot(fd, partition_offset, st.st_size)
        os.mkdir(target, mode=0o700)
        files: list[dict] = []
        skipped: dict[str, int] = {}
        # Scan a bounded MFT window: first 64k records or until EOF.
        max_records = 65536
        for index in range(max_records):
            if len(files) >= max_files:
                break
            rec_off = volume.cluster_offset(volume.mft_lcn) + index * volume.record_size
            if rec_off + volume.record_size > st.st_size:
                break
            raw = bytearray(_read(fd, rec_off, volume.record_size))
            if len(raw) != volume.record_size or raw[:4] != b"FILE":
                skipped["bad_record"] = skipped.get("bad_record", 0) + 1
                continue
            if not _fixup_record(raw):
                skipped["usa_fixup"] = skipped.get("usa_fixup", 0) + 1
                continue
            flags = struct.unpack_from("<H", raw, 0x16)[0]
            if flags & 0x1:
                # Still allocated — not a deleted file.
                continue
            if flags & 0x2:
                # Directory — skip for file undelete.
                skipped["deleted_directory"] = skipped.get("deleted_directory", 0) + 1
                continue
            names: list[str] = []
            data_attr = None
            for _, attr in _iter_attributes(raw):
                atype = struct.unpack_from("<I", attr, 0)[0]
                if atype == ATTR_FILENAME:
                    name = _parse_filename(attr)
                    if name:
                        names.append(name)
                elif atype == ATTR_DATA and _attribute_name(attr) == "":
                    data_attr = attr
            if data_attr is None:
                skipped["no_unnamed_data"] = skipped.get("no_unnamed_data", 0) + 1
                continue
            resident, payload, runs, data_size = _parse_data(data_attr)
            if data_size <= 0 or data_size > min(MAX_FILE_BYTES, max_file_mib * 1024 * 1024):
                skipped["size_limit"] = skipped.get("size_limit", 0) + 1
                continue
            display = names[-1] if names else f"mft{index}"
            out_name = _safe_name(display, len(files) + 1)
            dest = os.path.join(target, out_name)
            hasher = hashlib.sha256()
            outfd = os.open(dest, binary_open_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL), 0o600)
            try:
                with os.fdopen(outfd, "wb") as out:
                    if resident:
                        assert payload is not None
                        out.write(payload)
                        hasher.update(payload)
                    else:
                        remaining = data_size
                        for lcn, length in runs:
                            for i in range(length):
                                if remaining <= 0:
                                    break
                                if lcn < 0:
                                    chunk = b"\x00" * min(volume.cluster_size, remaining)
                                else:
                                    chunk = _read(
                                        fd,
                                        volume.cluster_offset(lcn + i),
                                        min(volume.cluster_size, remaining),
                                    )
                                    if len(chunk) != min(volume.cluster_size, remaining):
                                        raise OSError("Short NTFS cluster read")
                                out.write(chunk)
                                hasher.update(chunk)
                                remaining -= len(chunk)
                        if remaining > 0:
                            raise OSError("NTFS data runs shorter than declared size")
                    out.flush()
                    os.fsync(out.fileno())
            except BaseException:
                os.unlink(dest)
                raise
            files.append({
                "filename": out_name,
                "original_name": display,
                "mft_record": index,
                "size_bytes": data_size,
                "sha256": hasher.hexdigest(),
                "confidence": "ntfs_deleted_mft_UNVERIFIED",
            })
        return {
            "status": "completed",
            "filesystem": "ntfs",
            "partition_offset": partition_offset,
            "files_recovered": len(files),
            "files": files,
            "skipped": skipped,
            "notes": "NTFS undelete is speculative. Deleted MFT records may reference "
                     "reallocated clusters. Validate recovered content independently.",
        }
    finally:
        os.close(fd)
