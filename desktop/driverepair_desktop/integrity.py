"""Evidence-based, read-only image integrity audit and verified-copy repair.

These are *reference hashes*, not hardware ECC and not general-purpose bit repair.
No physical device writes; all repairs create NEW regular-file images.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys

from .compat import binary_open_flags
from .scanner import ImageReader
from .recovery import _write_all

_MAX_MANIFEST_BYTES = 128 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _check_new_file(path: str, *sources: str) -> str:
    absolute = os.path.abspath(path)
    if os.path.lexists(absolute):
        raise FileExistsError('Output already exists; use a NEW file to preserve existing evidence')
    if not os.path.isdir(os.path.dirname(absolute)):
        raise ValueError('Output parent directory does not exist')
    test = absolute.replace('\\', '/').lower()
    if test.startswith('/dev/') or test.startswith('//./') or test.startswith('//?/'):
        raise ValueError('Raw device outputs are forbidden')
    if any(os.path.realpath(absolute) == os.path.realpath(src) for src in sources):
        raise ValueError('Output overlaps an input')
    return absolute


def _identity(fd: int) -> tuple[int, int, int, int]:
    s = os.fstat(fd)
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns


def _ensure_unchanged(fd: int, initial: tuple[int, int, int, int]):
    if _identity(fd) != initial:
        raise RuntimeError('Input image changed during integrity operation; results invalid')


def _read_exact(reader: ImageReader, start: int, size: int) -> bytes:
    result = reader.read_at(start, size)
    if len(result) != size:
        raise OSError(f'Short image read at {start}: {len(result)} of {size}')
    return result


def _atomic_new_json(path: str, value: dict):
    """Write new JSON with private permissions; never overwrite a manifest."""
    path = _check_new_file(path)
    fd = os.open(path, binary_open_flags(
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)), 0o600)
    try:
        data = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
        _write_all(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    if os.name == 'posix':
        d = os.open(os.path.dirname(path), os.O_RDONLY)
        try:
            os.fsync(d)
        finally:
            os.close(d)


def build_manifest(image: str, output: str, *, chunk_mib: int = 16) -> dict:
    """Create hashes from a pre-existing stable image. Baseline quality is NOT inferred."""
    if not 1 <= chunk_mib <= 64:
        raise ValueError('Chunk size must be 1..64 MiB')
    output = _check_new_file(output, image)
    reader = ImageReader(image)
    try:
        initial = _identity(reader.fd)
        size = initial[2]
        if size <= 0:
            raise ValueError('Empty image')
        step = chunk_mib * 1024 * 1024
        count = (size + step - 1) // step
        if count > 1_000_000:
            raise ValueError('Manifest too large; use a larger chunk size')
        entries, whole = [], hashlib.sha256()
        for pos in range(0, size, step):
            data = _read_exact(reader, pos, min(step, size - pos))
            whole.update(data)
            entries.append(hashlib.sha256(data).hexdigest())
        _ensure_unchanged(reader.fd, initial)
    finally:
        reader.close()
    report = {'schema': 1, 'algorithm': 'sha256', 'size_bytes': size,
              'chunk_bytes': step, 'full_sha256': whole.hexdigest(), 'chunks': entries,
              'trust': 'UNATTESTED_BASELINE',
              'warning': 'Hashes reflect this image at creation time. If it was corrupt then, hashes preserve that corruption. Keep an independently trusted baseline.'}
    _atomic_new_json(output, report)
    return {'status': 'manifest_created_unattested', 'manifest': output,
            'image_bytes': size, 'chunks': count, 'chunk_bytes': step,
            'full_sha256': whole.hexdigest(), 'notes': report['warning']}


def _load_manifest(path: str) -> dict:
    if not stat.S_ISREG(os.lstat(path).st_mode):
        raise ValueError('Manifest is not a regular file')
    if os.stat(path).st_size > _MAX_MANIFEST_BYTES:
        raise ValueError('Manifest exceeds safe size limit')
    with open(path, encoding='utf-8') as f:
        m = json.load(f)
    if not isinstance(m, dict) or m.get('schema') != 1 or m.get('algorithm') != 'sha256':
        raise ValueError('Unsupported integrity manifest schema')
    size, step, hashes = m.get('size_bytes'), m.get('chunk_bytes'), m.get('chunks')
    if (type(size) is not int or size <= 0 or type(step) is not int or
            not 1024 * 1024 <= step <= 64 * 1024 * 1024 or
            not isinstance(hashes, list) or len(hashes) > 1_000_000 or
            len(hashes) != (size + step - 1) // step or
            any(not isinstance(x, str) or not _SHA256.fullmatch(x) for x in hashes) or
            not isinstance(m.get('full_sha256'), str) or not _SHA256.fullmatch(m['full_sha256'])):
        raise ValueError('Malformed or oversized integrity manifest')
    return m


def _untrusted_recovery_regions(image: str, size: int) -> list[tuple[int, int]]:
    """Unknown areas in incomplete rescue output must not count as bit flips."""
    map_path = os.path.abspath(image) + '.rescue.json'
    if not os.path.lexists(map_path):
        return []
    if not stat.S_ISREG(os.lstat(map_path).st_mode) or os.stat(map_path).st_size > _MAX_MANIFEST_BYTES:
        raise ValueError('Unsafe recovery journal')
    with open(map_path, encoding='utf-8') as f:
        state = json.load(f)
    if state.get('size') != size or os.path.realpath(state.get('output', '')) != os.path.realpath(image):
        raise ValueError('Recovery journal does not match the selected image')
    from .recovery import _validate_state
    _validate_state(state)
    regions = [(int(a), int(a + length)) for key in ('missing_ranges', 'retry_pending_ranges')
               for a, length in state.get(key, [])]
    cursor = state['cursor']
    if cursor < size:
        regions.append((cursor, size))
    return sorted(regions)


def _evaluate(image: str, manifest: dict, *, max_details: int = 2048) -> dict:
    reader = ImageReader(image)
    try:
        initial = _identity(reader.fd)
        size, step = manifest['size_bytes'], manifest['chunk_bytes']
        if initial[2] != size:
            raise ValueError('Image size does not match integrity manifest')
        unknowns = _untrusted_recovery_regions(image, size)
        mismatches, unknown_details = [], []
        verified = unknown = mismatch_count = 0
        r = 0
        for i, expected in enumerate(manifest['chunks']):
            offset = i * step
            length = min(step, size - offset)
            while r < len(unknowns) and unknowns[r][1] <= offset:
                r += 1
            if r < len(unknowns) and unknowns[r][0] < offset + length:
                unknown += 1
                if len(unknown_details) < max_details:
                    unknown_details.append({'index': i, 'offset': offset, 'length': length,
                                            'reason': 'Unvisited or unreadable rescue extent'})
                continue
            try:
                actual = hashlib.sha256(_read_exact(reader, offset, length)).hexdigest()
            except OSError:
                unknown += 1
                if len(unknown_details) < max_details:
                    unknown_details.append({'index': i, 'offset': offset, 'length': length,
                                            'reason': 'Read error during integrity audit'})
                continue
            if actual == expected:
                verified += 1
            else:
                mismatch_count += 1
                if len(mismatches) < max_details:
                    mismatches.append({'index': i, 'offset': offset, 'length': length,
                                       'observed_sha256': actual, 'expected_sha256': expected})
        _ensure_unchanged(reader.fd, initial)
        return {'status': ('integrity_mismatch' if mismatch_count else
                           'incomplete_unknown_regions' if unknown else 'matches_unattested_manifest'),
                'image_size_bytes': size, 'total_chunks': len(manifest['chunks']),
                'hash_matched_chunks': verified, 'hash_mismatched_chunks': mismatch_count,
                'unknown_chunks': unknown, 'mismatched_regions': mismatches,
                'unknown_regions': unknown_details,
                'details_truncated': mismatch_count > len(mismatches) or unknown > len(unknown_details),
                'notes': 'Hash matches prove agreement with THIS baseline only, not that the baseline was correct. '
                         'Unknown rescue gaps are not interpreted as zeroes or repaired data.'}
    finally:
        reader.close()


def audit_image(image: str, manifest_path: str) -> dict:
    return _evaluate(image, _load_manifest(manifest_path))


def _try_linux_reflink(src_fd: int, dest_fd: int) -> bool:
    """Use filesystem copy-on-write clone when available; transparent safe fallback.

    FICLONE is supported by some modern Linux filesystems (e.g., Btrfs/XFS).
    It shares physical extents until modified, not an in-place source rewrite.
    """
    if not sys.platform.startswith('linux'):
        return False
    try:
        import fcntl
        fcntl.ioctl(dest_fd, 0x40049409, src_fd)  # Linux FICLONE ioctl.
        return True
    except OSError:
        # Some unsupported filesystems could leave a partially initialized clone.
        # The output is a NEW regular file, so resetting it does not affect input.
        os.ftruncate(dest_fd, 0)
        os.lseek(dest_fd, 0, os.SEEK_SET)
        return False


def restore_image_from_reference(image: str, reference: str, manifest_path: str,
                                 output: str, *, allow_incomplete: bool = False) -> dict:
    """Create NEW image with only mismatched chunks replaced from hash-verified reference.

    Never writes to patient disk, candidate image, or reference. Refuses unknown
    recovery regions by default, because writing zeros into a fresh copy could
    wrongly imply that data was recovered.
    """
    m = _load_manifest(manifest_path)
    output = _check_new_file(output, image, reference, manifest_path)
    if os.path.samefile(image, reference):
        raise ValueError('Reference cannot be the candidate itself')
    a, ref = ImageReader(image), ImageReader(reference)
    fd = None
    try:
        sa, sr = _identity(a.fd), _identity(ref.fd)
        size, step = m['size_bytes'], m['chunk_bytes']
        if sa[2] != size or sr[2] != size:
            raise ValueError('Candidate/reference dimensions do not match manifest')
        unknowns = _untrusted_recovery_regions(image, size)
        if _untrusted_recovery_regions(reference, size):
            raise ValueError('Reference rescue image still has unknown/unreadable areas')
        if unknowns and not allow_incomplete:
            raise ValueError('Candidate rescue map has unknown/unreadable regions; refusing a full-image integrity claim')
        # The new output MUST NOT be a physical device, and must not already exist.
        # O_BINARY is required on Windows — text-mode translation expands 0x0A and
        # silently corrupts restored disk images (size/hash mismatch).
        fd = os.open(output, binary_open_flags(
            os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)), 0o600)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Output must be a regular file')
        reflinked = _try_linux_reflink(a.fd, fd)
        fixed, unverifiable = 0, 0
        whole = hashlib.sha256()
        bad_reference = []
        for i, expected in enumerate(m['chunks']):
            off = i * step
            count = min(step, size - off)
            data = _read_exact(a, off, count)
            changed = hashlib.sha256(data).hexdigest() != expected
            patched = False
            if changed:
                alternative = _read_exact(ref, off, count)
                if hashlib.sha256(alternative).hexdigest() == expected:
                    data = alternative
                    fixed += 1
                    patched = True
                else:
                    unverifiable += 1
                    if len(bad_reference) < 2048:
                        bad_reference.append({'offset': off, 'length': count})
            if not reflinked:
                _write_all(fd, data)
            elif patched:
                _write_all(fd, data, off)
            whole.update(data)
        os.fsync(fd)
        _ensure_unchanged(a.fd, sa)
        _ensure_unchanged(ref.fd, sr)
        # Read back output for independent verification, not merely a hash of
        # the source bytes we *intended* to write. Never report verified on
        # failed/partial writes, nor when the original recovery map has gaps.
        result = _evaluate(output, m, max_details=64)
        good = (unverifiable == 0 and not unknowns and
                result['hash_mismatched_chunks'] == 0 and result['unknown_chunks'] == 0 and
                whole.hexdigest() == m['full_sha256'])
        return {'status': 'verified_restored_copy' if good else 'incomplete_unverified_copy',
                'output': output, 'size_bytes': size, 'replaced_chunks': fixed,
                'unverified_chunks': unverifiable, 'reference_failures': bad_reference,
                'intended_output_sha256': whole.hexdigest(), 'matches_manifest_sha256': good,
                'output_readback': result['status'],
                'copy_strategy': 'linux_reflink_copy_on_write' if reflinked else 'streaming_copy',
                'notes': 'Only a NEW image was written. The source and existing image were not modified. '
                         'No arbitrary bit flip can be corrected without verified reference data.'}
    finally:
        if fd is not None:
            os.close(fd)
        a.close()
        ref.close()
