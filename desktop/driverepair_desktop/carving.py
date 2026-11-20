"""Non-destructive, signature-based media/document carving from regular-file images.

Supported signatures:
  - PNG (chunk CRC validated)
  - JPEG (SOI/EOI heuristic)
  - MP4/M4V/MOV-style ISO BMFF (`ftyp` box walk)
  - PDF (`%PDF-` … `%%EOF`)
  - Legacy Office OLE/CFB (`.doc` / `.xls` classified by stream names)
  - OOXML Office ZIP (`.docx` / `.xlsx` via local headers + EOCD)

Plain `.txt` is not carved from free space (too many false positives); recover
named deleted text via `undelete-fat32` after imaging. Carving cannot prove a
hit was deleted, recover paths, or reconstruct fragmented files.
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
PDF_SIG = b'%PDF-'
OLE_SIG = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
ZIP_SIG = b'PK\x03\x04'
ZIP_EOCD_SIG = b'PK\x05\x06'
FTYP_TAG = b'ftyp'
MP4_BRANDS = {
    b'isom', b'iso2', b'iso3', b'iso4', b'iso5', b'iso6',
    b'mp41', b'mp42', b'avc1', b'M4V ', b'M4A ', b'qt  ',
    b'3gp4', b'3gp5', b'3gp6', b'MSNV', b'NDSC', b'NDSH',
    b'NDSM', b'NDSP', b'NDSS', b'NDXC', b'NDXH', b'NDXM',
    b'NDXP', b'NDXS', b'XAVC',
}
SUPPORTED_FORMATS = frozenset({
    'png', 'jpeg', 'mp4', 'pdf', 'ole', 'doc', 'xls', 'docx', 'xlsx',
})
WINDOW = 1024 * 1024
MP4_MIN_BYTES = 32
MP4_MAX_BOXES = 200000
PDF_MIN_BYTES = 32
OLE_MIN_BYTES = 512
ZIP_MIN_BYTES = 64


def _read_at(fd: int, offset: int, count: int) -> bytes:
    """Read `count` bytes at `offset`.

    On Windows, raw volume/physical handles often reject unaligned seeks; always
    read through a 512-byte aligned window and slice. Regular files accept this too.
    """
    if count <= 0:
        return b''
    if hasattr(os, 'pread') and os.name != 'nt':
        return os.pread(fd, count, offset)
    align = 512
    aligned_off = offset - (offset % align)
    skip = offset - aligned_off
    need = skip + count
    need = ((need + align - 1) // align) * align
    if hasattr(os, 'pread'):
        data = os.pread(fd, need, aligned_off)
    else:
        os.lseek(fd, aligned_off, os.SEEK_SET)
        data = os.read(fd, need)
    if len(data) <= skip:
        return b''
    return data[skip:skip + count]


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


def _mp4_box_size(header: bytes, remaining: int) -> int | None:
    if len(header) < 8:
        return None
    size: int = struct.unpack('>I', header[:4])[0]
    if size == 0:
        return None
    if size == 1:
        if len(header) < 16:
            return None
        size = int(struct.unpack('>Q', header[8:16])[0])
        if size < 16:
            return None
    elif size < 8:
        return None
    if size > remaining:
        return None
    return size


def _mp4(fd: int, start: int, size: int, limit: int) -> bytes | None:
    if start + 12 > size:
        return None
    head = _read_at(fd, start, 16)
    if len(head) < 12 or head[4:8] != FTYP_TAG:
        return None
    box0 = _mp4_box_size(head, min(limit, size - start))
    if box0 is None or box0 < 16:
        return None
    brand = _read_at(fd, start + 8, 4)
    if len(brand) != 4 or brand not in MP4_BRANDS:
        return None
    position = start
    end_cap = min(size, start + limit)
    boxes = 0
    saw_mdat = False
    while position + 8 <= end_cap and boxes < MP4_MAX_BOXES:
        header = _read_at(fd, position, 16)
        if len(header) < 8:
            break
        kind = header[4:8]
        if not all(32 <= b < 127 for b in kind):
            break
        box_size = _mp4_box_size(header, end_cap - position)
        if box_size is None:
            break
        if kind == b'mdat':
            saw_mdat = True
        position += box_size
        boxes += 1
    total = position - start
    if total < MP4_MIN_BYTES or boxes < 2 or not saw_mdat:
        return None
    return _read_at(fd, start, total)


def _pdf(fd: int, start: int, size: int, limit: int) -> bytes | None:
    head = _read_at(fd, start, 8)
    if len(head) < 5 or not head.startswith(PDF_SIG):
        return None
    # Version digit after %PDF-
    if not (len(head) >= 8 and 48 <= head[5] <= 57):
        return None
    cap = min(size, start + limit)
    cursor = start
    last_eof = -1
    carry = b''
    while cursor < cap:
        block = _read_at(fd, cursor, min(WINDOW, cap - cursor))
        if not block:
            break
        buf = carry + block
        pos = 0
        while (pos := buf.find(b'%%EOF', pos)) >= 0:
            abs_pos = cursor - len(carry) + pos
            end = abs_pos + 5
            # Consume optional CR/LF after %%EOF
            trail = _read_at(fd, end, 2)
            if trail.startswith(b'\r\n'):
                end += 2
            elif trail.startswith(b'\n') or trail.startswith(b'\r'):
                end += 1
            last_eof = end
            pos += 5
        carry = buf[-4:]
        cursor += len(block)
    if last_eof < 0 or last_eof - start < PDF_MIN_BYTES:
        return None
    return _read_at(fd, start, last_eof - start)


def _ole_classify(sample: bytes) -> str:
    # Stream names are stored as UTF-16LE in the CFB directory.
    if b'W\x00o\x00r\x00d\x00D\x00o\x00c\x00u\x00m\x00e\x00n\x00t\x00' in sample:
        return 'doc'
    if b'W\x00o\x00r\x00k\x00b\x00o\x00o\x00k\x00' in sample:
        return 'xls'
    if b'B\x00o\x00o\x00k\x00' in sample and b'W\x00o\x00r\x00k\x00b\x00o\x00o\x00k\x00' in sample:
        return 'xls'
    return 'ole'


def _ole(fd: int, start: int, size: int, limit: int) -> tuple[bytes, str] | None:
    header = _read_at(fd, start, 512)
    if len(header) < 512 or header[:8] != OLE_SIG:
        return None
    sector_shift = struct.unpack_from('<H', header, 30)[0]
    if sector_shift not in {9, 12}:  # 512 or 4096 byte sectors
        return None
    sector_size = 1 << sector_shift
    # Number of FAT sectors (offset 44) gives a weak upper bound.
    fat_sectors = struct.unpack_from('<I', header, 44)[0]
    if fat_sectors > 1_000_000:
        return None
    # Conservative span: header + FAT estimate, capped by limit.
    estimate = sector_size * (fat_sectors + 2)
    if estimate < OLE_MIN_BYTES:
        estimate = min(limit, 64 * 1024)
    total = min(limit, size - start, max(estimate, 8 * sector_size))
    if total < OLE_MIN_BYTES:
        return None
    content = _read_at(fd, start, total)
    if len(content) < OLE_MIN_BYTES:
        return None
    kind = _ole_classify(content[: min(len(content), 256 * 1024)])
    return content, kind


def _zip_eocd_size(fd: int, start: int, size: int, limit: int) -> int | None:
    """Return total ZIP length from start if a plausible EOCD is found."""
    cap = min(size, start + limit)
    # EOCD is at the end; search the trailing window.
    search_start = max(start, cap - min(65_535 + 22, limit))
    data = _read_at(fd, search_start, cap - search_start)
    pos = data.rfind(ZIP_EOCD_SIG)
    if pos < 0 or pos + 22 > len(data):
        return None
    comment_len = struct.unpack_from('<H', data, pos + 20)[0]
    eocd_end = search_start + pos + 22 + comment_len
    if eocd_end > cap or eocd_end <= start:
        return None
    total = int(eocd_end - start)
    if total < ZIP_MIN_BYTES:
        return None
    return total


def _ooxml(fd: int, start: int, size: int, limit: int, want: str) -> bytes | None:
    if _read_at(fd, start, 4) != ZIP_SIG:
        return None
    total = _zip_eocd_size(fd, start, size, limit)
    if total is None:
        return None
    content = _read_at(fd, start, total)
    # Cheap content-type checks without full ZIP parse.
    if want == 'docx' and (b'word/' in content or b'word\\' in content):
        return content
    if want == 'xlsx' and (b'xl/' in content or b'xl\\' in content):
        return content
    return None


def _extract(fmt: str, fd: int, start: int, size: int, limit: int):
    """Return bytes, or (bytes, resolved_fmt) for OLE family."""
    if fmt == 'png':
        return _png(fd, start, size, limit)
    if fmt == 'jpeg':
        return _jpeg(fd, start, size, limit)
    if fmt == 'mp4':
        return _mp4(fd, start, size, limit)
    if fmt == 'pdf':
        return _pdf(fd, start, size, limit)
    if fmt in {'ole', 'doc', 'xls'}:
        got = _ole(fd, start, size, limit)
        if got is None:
            return None
        content, kind = got
        if fmt in {'doc', 'xls'} and kind != fmt and kind != 'ole':
            # Caller asked for a specific Office type; allow ole→requested only
            # when classification matched or stayed generic.
            if kind != fmt:
                return None
        if fmt == 'ole':
            return content, kind
        return content, fmt if kind == 'ole' else kind
    if fmt == 'docx':
        return _ooxml(fd, start, size, limit, 'docx')
    if fmt == 'xlsx':
        return _ooxml(fd, start, size, limit, 'xlsx')
    return None


def _confidence(fmt: str) -> str:
    return {
        'png': 'png_chunk_crc_valid',
        'jpeg': 'jpeg_signature_and_end_marker_only',
        'mp4': 'mp4_ftyp_brand_and_box_walk',
        'pdf': 'pdf_header_and_eof_marker',
        'ole': 'ole_cfb_header_heuristic',
        'doc': 'ole_cfb_worddocument_stream',
        'xls': 'ole_cfb_workbook_stream',
        'docx': 'ooxml_zip_word_hint',
        'xlsx': 'ooxml_zip_xl_hint',
    }[fmt]


def _extension(fmt: str) -> str:
    return {
        'png': 'png', 'jpeg': 'jpg', 'mp4': 'mp4', 'pdf': 'pdf',
        'ole': 'ole', 'doc': 'doc', 'xls': 'xls',
        'docx': 'docx', 'xlsx': 'xlsx',
    }[fmt]


def _signature_scanners(formats: tuple[str, ...]) -> list[tuple[str, bytes, int]]:
    """(format, needle, start_adjust) scanners for one window."""
    scanners: list[tuple[str, bytes, int]] = []
    simple = (
        ('png', PNG_SIG),
        ('jpeg', JPG_SIG),
        ('pdf', PDF_SIG),
    )
    for fmt, sig in simple:
        if fmt in formats:
            scanners.append((fmt, sig, 0))
    ole_aliases = [f for f in ('ole', 'doc', 'xls') if f in formats]
    if ole_aliases:
        # One OLE hit is enough; classification picks doc/xls/ole later.
        fmt = 'doc' if 'doc' in ole_aliases else ('xls' if 'xls' in ole_aliases else 'ole')
        if len(ole_aliases) > 1 or 'ole' in ole_aliases:
            fmt = 'ole'
        scanners.append((fmt, OLE_SIG, 0))
    if 'mp4' in formats:
        scanners.append(('mp4', FTYP_TAG, -4))
    for fmt in ('docx', 'xlsx'):
        if fmt in formats:
            scanners.append((fmt, ZIP_SIG, 0))
    return scanners


def _iter_signature_hits(formats: tuple[str, ...], buffer: bytes, base: int):
    """Yield signature hits in ascending offset order without materializing all matches.

    Dense synthetic windows can contain hundreds of thousands of candidate
    offsets per MiB; sorting a full materialization would OOM. Callers stop
    after max_files successful extracts.
    """
    import heapq

    def _next_hit(needle: bytes, adjust: int, from_pos: int) -> tuple[int, int] | None:
        pos = from_pos
        while True:
            pos = buffer.find(needle, pos)
            if pos < 0:
                return None
            start = base + pos + adjust
            if start >= 0:
                return start, pos + 1
            pos += 1

    scanners = _signature_scanners(formats)
    heap: list[tuple[int, int, str, int]] = []  # offset, scanner_idx, fmt, next_search
    for idx, (fmt, needle, adjust) in enumerate(scanners):
        hit = _next_hit(needle, adjust, 0)
        if hit is not None:
            start, nxt = hit
            heapq.heappush(heap, (start, idx, fmt, nxt))
    while heap:
        start, idx, fmt, next_pos = heapq.heappop(heap)
        yield start, fmt
        needle, adjust = scanners[idx][1], scanners[idx][2]
        hit = _next_hit(needle, adjust, next_pos)
        if hit is not None:
            nxt_start, nxt = hit
            heapq.heappush(heap, (nxt_start, idx, fmt, nxt))


def _signature_hits(formats: tuple[str, ...], buffer: bytes, base: int) -> list[tuple[int, str]]:
    """Compatibility helper for tests; prefer _iter_signature_hits in carve loops."""
    return list(_iter_signature_hits(formats, buffer, base))


def carve_image(image: str, dest: str, *, formats: tuple[str, ...] = ('png', 'jpeg'),
                max_files: int = 100, max_file_mib: int = 32,
                allow_incomplete: bool = False) -> dict:
    if (not formats or set(formats) - SUPPORTED_FORMATS or
            not 1 <= max_files <= 10000 or not 1 <= max_file_mib <= 512):
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
        overlap = max(len(PNG_SIG), len(JPG_SIG), len(PDF_SIG), len(OLE_SIG), 12) - 1
        tail = b''
        cursor = 0
        limit = max_file_mib * WINDOW
        while cursor < st.st_size and len(results) < max_files:
            data = _read_at(source, cursor, min(WINDOW, st.st_size - cursor))
            if not data:
                break
            buffer = tail + data
            base = cursor - len(tail)
            for start, fmt in _iter_signature_hits(formats, buffer, base):
                if start in seen_offsets or len(results) >= max_files:
                    continue
                seen_offsets.add(start)
                extracted = _extract(fmt, source, start, st.st_size, limit)
                if extracted is None:
                    continue
                if isinstance(extracted, tuple):
                    content, resolved = extracted
                else:
                    content, resolved = extracted, fmt
                name = f'{len(results) + 1:05d}_{start:016x}.{_extension(resolved)}'
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
                                'format': resolved,
                                'confidence': _confidence(resolved)})
            tail = buffer[-overlap:]
            cursor += len(data)
        return {'status': 'completed', 'files': results, 'files_carved': len(results),
                'notes': 'Carved content may be existing, deleted, stale or fragmented. '
                         'JPEG/MP4/PDF/OLE/OOXML are heuristic. Plain text is not carved; '
                         'use undelete-fat32 for named .txt deletions. '
                         'Does not reconstruct missing bytes.'}
    finally:
        os.close(source)
