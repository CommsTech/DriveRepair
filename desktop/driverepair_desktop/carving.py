"""Non-destructive, signature-based JPEG/PNG carving from *regular file images*.

Not a complete undelete tool: cannot prove that carved files were deleted,
recover names/paths, reconstruct fragmented files, or repair unknown bytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import struct
import zlib

from .compat import binary_open_flags

PNG_SIG = b'\x89PNG\r\n\x1a\n'
JPG_SIG = b'\xff\xd8\xff'
WINDOW = 1024 * 1024


def _read_at(fd: int, offset: int, count: int) -> bytes:
    if hasattr(os, 'pread'):
        return os.pread(fd, count, offset)
    os.lseek(fd, offset, os.SEEK_SET)
    return os.read(fd, count)


def _png(fd: int, start: int, size: int, limit: int) -> bytes | None:
    position = start + len(PNG_SIG)
    if _read_at(fd, start, len(PNG_SIG)) != PNG_SIG:
        return None
    total = len(PNG_SIG)
    chunks = 0
    result = bytearray(PNG_SIG)
    seen_ihdr = False
    seen_idat = False
    while position + 12 <= size and total + 12 <= limit and chunks < 10000:
        header = _read_at(fd, position, 8)
        if len(header) != 8:
            return None
        n, kind = struct.unpack('>I4s', header)
        if n > limit - total - 12 or position + n + 12 > size:
            return None
        if not all(65 <= k <= 90 or 97 <= k <= 122 for k in kind):
            return None
        if not seen_ihdr:
            if kind != b'IHDR' or n != 13:
                return None
            seen_ihdr = True
        if kind == b'IDAT':
            seen_idat = True
        data = _read_at(fd, position + 8, n + 4)
        if len(data) != n + 4:
            return None
        expected = struct.unpack('>I', data[-4:])[0]
        if zlib.crc32(kind + data[:-4]) & 0xffffffff != expected:
            return None
        result.extend(header)
        result.extend(data)
        position += n + 12
        total += n + 12
        chunks += 1
        if kind == b'IEND':
            if n != 0 or not seen_idat:
                return None
            return bytes(result)
    return None


def _jpeg(fd: int, start: int, size: int, limit: int) -> bytes | None:
    # Best-effort end marker. JPEG can have false positives and fragmented files;
    # report less-than-verified confidence, unlike CRC-validated PNG chunks.
    if _read_at(fd, start, 3) != JPG_SIG:
        return None
    collected = bytearray()
    cursor = start
    cap = min(size, start + limit)
    while cursor < cap:
        block = _read_at(fd, cursor, min(WINDOW, cap - cursor))
        if not block:
            break
        old_len = len(collected)
        collected.extend(block)
        pos = collected.find(b'\xff\xd9', max(3, old_len - 1))
        if pos >= 0:
            return bytes(collected[:pos + 2]) if pos >= 64 else None
        cursor += len(block)
    return None


def carve_image(image: str, dest: str, *, formats: tuple[str, ...] = ('png', 'jpeg'),
                max_files: int = 100, max_file_mib: int = 32,
                allow_incomplete: bool = False) -> dict:
    if (not formats or set(formats) - {'png', 'jpeg'} or
            not 1 <= max_files <= 10000 or not 1 <= max_file_mib <= 256):
        raise ValueError('Invalid carving arguments')
    image = os.path.abspath(image)
    dest = os.path.abspath(dest)
    if image.replace('\\', '/').startswith('/dev/') or image.startswith('\\\\.\\'):
        raise ValueError('Carving requires a regular image file, not a raw device')
    source = os.open(image, binary_open_flags(os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)))
    try:
        st = os.fstat(source)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError('Carving source must be regular file')
        journal = image + '.rescue.json'
        if os.path.exists(journal) and not allow_incomplete:
            with open(journal, encoding='utf-8') as f:
                status = json.load(f)
            if status.get('status') != 'completed':
                raise RuntimeError('Image has missing/unverified sectors; '
                                   'use --allow-incomplete-image acknowledging limitations')
        if os.path.commonpath((os.path.realpath(image), os.path.realpath(dest))) == os.path.realpath(image):
            raise ValueError('Destination may not be source image')
        if os.path.exists(dest):
            raise FileExistsError('Destination directory already exists; choose an empty new directory')
        os.mkdir(dest, 0o700)
        results: list[dict] = []
        seen_offsets: set[int] = set()
        overlap = max(len(PNG_SIG), len(JPG_SIG)) - 1
        tail = b''
        cursor = 0
        while cursor < st.st_size and len(results) < max_files:
            data = _read_at(source, cursor, min(WINDOW, st.st_size - cursor))
            if not data:
                break
            buffer = tail + data
            base = cursor - len(tail)
            positions: list[tuple[int, str]] = []
            for fmt, sig in (('png', PNG_SIG), ('jpeg', JPG_SIG)):
                if fmt not in formats:
                    continue
                pos = 0
                while (pos := buffer.find(sig, pos)) >= 0:
                    positions.append((base + pos, fmt))
                    pos += 1
            for start, fmt in sorted(positions):
                if start in seen_offsets or len(results) >= max_files:
                    continue
                seen_offsets.add(start)
                content = (_png(source, start, st.st_size, max_file_mib * WINDOW)
                           if fmt == 'png' else
                           _jpeg(source, start, st.st_size, max_file_mib * WINDOW))
                if content is None:
                    continue
                name = f'{len(results) + 1:05d}_{start:016x}.{("jpg" if fmt == "jpeg" else fmt)}'
                path = os.path.join(dest, name)
                fd = os.open(path, binary_open_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL), 0o600)
                try:
                    with os.fdopen(fd, 'wb') as out:
                        out.write(content)
                        out.flush()
                        os.fsync(out.fileno())
                except BaseException:
                    os.unlink(path)
                    raise
                results.append({'filename': name, 'offset_bytes': start,
                                'size_bytes': len(content),
                                'sha256': hashlib.sha256(content).hexdigest(),
                                'confidence': ('png_chunk_crc_valid' if fmt == 'png'
                                               else 'jpeg_signature_and_end_marker_only')})
            tail = buffer[-overlap:]
            cursor += len(data)
        return {'status': 'completed', 'files': results, 'files_carved': len(results),
                'notes': 'Carved content may be existing, deleted, stale or fragmented. '
                         'JPEG is heuristic. Does not reconstruct missing bytes.'}
    finally:
        os.close(source)
