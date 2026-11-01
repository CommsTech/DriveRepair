"""Conservative FAT32 undelete from regular-file images only.

A FAT32 deleted directory entry may retain its original cluster and size even
when its allocation chain is cleared. This module can retrieve *contiguous*,
currently-unallocated clusters. It does not recover overwritten/fragmented data,
original first filename characters, or prove a recovered file is intact.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import struct
from dataclasses import dataclass

from .compat import binary_open_flags

MAX_FILE_BYTES = 2 * 1024**3


def _read(fd: int, offset: int, size: int) -> bytes:
    if hasattr(os, 'pread'):
        return os.pread(fd, size, offset)
    os.lseek(fd, offset, os.SEEK_SET)
    return os.read(fd, size)


@dataclass(frozen=True)
class Volume:
    start: int
    bytes_per_sector: int
    cluster_bytes: int
    fat_offset: int
    data_offset: int
    total_clusters: int
    root_cluster: int
    active_fat: int

    def cluster_offset(self, cluster: int) -> int:
        if not 2 <= cluster < self.total_clusters + 2:
            raise ValueError('FAT32 cluster outside data region')
        return self.data_offset + (cluster - 2) * self.cluster_bytes


def _parse_volume(fd: int, size: int, start: int) -> Volume | None:
    header = _read(fd, start, 512)
    if len(header) != 512 or header[510:512] != b'\x55\xaa':
        return None
    bps = struct.unpack_from('<H', header, 11)[0]
    spc = header[13]
    reserved = struct.unpack_from('<H', header, 14)[0]
    fats = header[16]
    root_count = struct.unpack_from('<H', header, 17)[0]
    fat16 = struct.unpack_from('<H', header, 22)[0]
    fat32 = struct.unpack_from('<I', header, 36)[0]
    total = struct.unpack_from('<I', header, 32)[0]
    root_cluster = struct.unpack_from('<I', header, 44)[0]
    fat_flags = struct.unpack_from('<H', header, 40)[0]
    if (bps not in {512, 1024, 2048, 4096} or spc == 0 or
            spc & (spc - 1) or spc > 128 or reserved < 1 or
            fats not in (1, 2) or root_count or fat16 or not fat32 or
            not total or root_cluster < 2 or
            (fat_flags & 0x80 and (fat_flags & 0xf) >= fats)):
        return None
    cluster_bytes = bps * spc
    data_sectors = total - reserved - fats * fat32
    if data_sectors <= 0 or start + total * bps > size:
        return None
    clusters = data_sectors // spc
    if clusters < 1 or clusters + 2 > fat32 * bps // 4:
        return None
    if root_cluster >= clusters + 2:
        return None
    active_fat = (fat_flags & 0xf) if fat_flags & 0x80 else 0
    return Volume(start, bps, cluster_bytes, start + (reserved + active_fat * fat32) * bps,
                  start + (reserved + fats * fat32) * bps, clusters, root_cluster, active_fat)


def _find_volume(fd: int, size: int) -> Volume:
    raw = _parse_volume(fd, size, 0)
    if raw:
        return raw
    sector = _read(fd, 0, 512)
    if len(sector) != 512 or sector[510:512] != b'\x55\xaa':
        raise ValueError('No FAT32 boot sector or MBR found; GPT/exFAT/NTFS not supported')
    for i in range(4):
        entry = sector[446 + i * 16:462 + i * 16]
        if entry[4] not in {0x0b, 0x0c, 0x1b, 0x1c}:
            continue
        lba, length = struct.unpack_from('<II', entry, 8)
        if not lba or not length or lba * 512 >= size:
            continue
        volume = _parse_volume(fd, size, lba * 512)
        if volume and volume.start + length * 512 <= size:
            return volume
    raise ValueError('No supported FAT32 filesystem found (raw volume or MBR partition)')


def _fat_entry(fd: int, volume: Volume, cluster: int) -> int:
    data = _read(fd, volume.fat_offset + cluster * 4, 4)
    if len(data) != 4:
        raise OSError('Short FAT read')
    return struct.unpack('<I', data)[0] & 0x0fffffff


def _chain(fd: int, volume: Volume, first: int, budget: int) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    cluster = first
    while len(result) < budget:
        if cluster in seen or not 2 <= cluster < volume.total_clusters + 2:
            raise ValueError('Corrupt or looping FAT directory chain')
        seen.add(cluster)
        result.append(cluster)
        nxt = _fat_entry(fd, volume, cluster)
        if nxt >= 0x0ffffff8:
            return result
        if nxt < 2 or nxt >= volume.total_clusters + 2:
            raise ValueError('Invalid FAT directory chain')
        cluster = nxt
    raise ValueError('FAT directory chain exceeds safety limit')


def _clean_name(entry: bytes) -> str:
    # Deletion overwrites the first character. Preserve only the remainder.
    stem = entry[1:8].decode('ascii', 'replace').rstrip(' ')
    ext = entry[8:11].decode('ascii', 'replace').rstrip(' ')
    name = '_' + stem + ('.' + ext if ext else '')
    return re.sub(r'[^A-Za-z0-9_.-]', '_', name)[:32]


def undelete_fat32(image: str, output_dir: str, *, max_files: int = 100,
                   max_file_mib: int = 128, allow_incomplete: bool = False) -> dict:
    """Recover plausibly intact, contiguous deleted files into a fresh directory.

    All files are flagged unverified; no directory entries or FAT are modified.
    """
    if not 1 <= max_files <= 10000 or not 1 <= max_file_mib <= 2048:
        raise ValueError('Invalid file limit')
    source = os.path.abspath(image)
    target = os.path.abspath(output_dir)
    if source.replace('\\', '/').lower().startswith(('/dev/', '//./', '//?/')):
        raise ValueError('Use a regular image file, never a raw disk')
    if not stat.S_ISREG(os.lstat(source).st_mode):
        raise ValueError('Source must be a regular file, not a symlink or device')
    fd = os.open(source, binary_open_flags(os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)))
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError('FAT32 undelete requires a regular disk image')
        journal = source + '.rescue.json'
        if os.path.exists(journal) and not allow_incomplete:
            with open(journal, encoding='utf-8') as f:
                state = json.load(f)
            if state.get('status') != 'completed':
                raise RuntimeError('Image contains missing ranges; explicitly allow incomplete image')
        if os.path.lexists(target):
            raise FileExistsError('Choose a new, nonexistent output directory')
        volume = _find_volume(fd, st.st_size)
        # Creating a directory only after source validation prevents empty outputs
        # on unsupported images. Do not descend through symlink targets.
        os.mkdir(target, 0o700)
        files: list[dict] = []
        skipped: dict[str, int] = {}
        visited_dirs: set[int] = set()
        queue = [volume.root_cluster]
        scanned_dirs = 0
        while queue and scanned_dirs < 10000 and len(files) < max_files:
            directory = queue.pop(0)
            if directory in visited_dirs:
                continue
            visited_dirs.add(directory)
            try:
                clusters = _chain(fd, volume, directory, 4096)
            except (ValueError, OSError):
                skipped['unreadable_directory'] = skipped.get('unreadable_directory', 0) + 1
                continue
            scanned_dirs += 1
            done = False
            for directory_cluster in clusters:
                block = _read(fd, volume.cluster_offset(directory_cluster), volume.cluster_bytes)
                if len(block) != volume.cluster_bytes:
                    raise OSError('Directory read truncated')
                for i in range(0, len(block), 32):
                    entry = block[i:i + 32]
                    first, attributes = entry[0], entry[11]
                    if first == 0:
                        done = True
                        break
                    if first != 0xe5:
                        if (attributes & 0x10 and not attributes & 0x08 and
                                attributes != 0x0f and first not in (0x2e,)):
                            child = (struct.unpack_from('<H', entry, 20)[0] << 16 |
                                     struct.unpack_from('<H', entry, 26)[0])
                            if 2 <= child < volume.total_clusters + 2:
                                queue.append(child)
                        continue
                    if attributes == 0x0f or attributes & 0x18:
                        continue
                    length = struct.unpack_from('<I', entry, 28)[0]
                    cluster = (struct.unpack_from('<H', entry, 20)[0] << 16 |
                               struct.unpack_from('<H', entry, 26)[0])
                    if length == 0 or length > min(MAX_FILE_BYTES, max_file_mib * 1024 * 1024):
                        skipped['size_limit'] = skipped.get('size_limit', 0) + 1
                        continue
                    required = (length + volume.cluster_bytes - 1) // volume.cluster_bytes
                    if (cluster < 2 or cluster + required > volume.total_clusters + 2):
                        skipped['invalid_cluster'] = skipped.get('invalid_cluster', 0) + 1
                        continue
                    if any(_fat_entry(fd, volume, c) != 0 for c in range(cluster, cluster + required)):
                        skipped['cluster_reallocated'] = skipped.get('cluster_reallocated', 0) + 1
                        continue
                    name = f'{len(files)+1:05d}_deleted_{_clean_name(entry)}'
                    dest = os.path.join(target, name)
                    hasher = hashlib.sha256()
                    outfd = os.open(dest, binary_open_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL), 0o600)
                    try:
                        with os.fdopen(outfd, 'wb') as out:
                            remaining = length
                            for c in range(cluster, cluster + required):
                                piece = _read(fd, volume.cluster_offset(c), min(volume.cluster_bytes, remaining))
                                if len(piece) != min(volume.cluster_bytes, remaining):
                                    raise OSError('Short read during file extraction')
                                out.write(piece)
                                hasher.update(piece)
                                remaining -= len(piece)
                            out.flush()
                            os.fsync(out.fileno())
                    except BaseException:
                        os.unlink(dest)
                        raise
                    files.append({'filename': name, 'size_bytes': length,
                                  'starting_cluster': cluster, 'sha256': hasher.hexdigest(),
                                  'confidence': 'contiguous_unallocated_clusters_UNVERIFIED'})
                    if len(files) >= max_files:
                        break
                if done or len(files) >= max_files:
                    break
        return {'status': 'completed', 'filesystem': 'FAT32', 'partition_offset': volume.start,
                'files_recovered': len(files), 'files': files, 'skipped': skipped,
                'notes': 'Recovery is speculative: the deleted first filename character is lost; '
                         'clusters may have been overwritten or originally fragmented. '
                         'Recovered files require independent validation.'}
    finally:
        os.close(fd)
