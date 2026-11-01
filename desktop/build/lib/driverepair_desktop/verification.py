"""Verify a rescued image against a stable known source-image file.

This reads BOTH images end to end. It is unsuitable for unstable live hardware,
and never proves that original source contents were uncorrupted to begin with.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat

from .scanner import ImageReader


def verify_images(source: str, candidate: str, *, chunk_mib: int = 4) -> dict:
    if not 1 <= chunk_mib <= 16:
        raise ValueError('Invalid verification chunk size')
    if os.path.samefile(source, candidate):
        raise ValueError('Source and candidate are the same file; comparison would be meaningless')
    a = ImageReader(source)
    b = ImageReader(candidate)
    try:
        before_a, before_b = os.fstat(a.fd), os.fstat(b.fd)
        if before_a.st_size != before_b.st_size:
            return {'status': 'size_mismatch', 'source_size': before_a.st_size,
                    'candidate_size': before_b.st_size}
        map_path = os.path.abspath(candidate) + '.rescue.json'
        map_status = None
        if os.path.lexists(map_path):
            if not stat.S_ISREG(os.lstat(map_path).st_mode):
                raise ValueError('Recovery map must be a regular file')
            with open(map_path, encoding='utf-8') as f:
                recovery = json.load(f)
            map_status = recovery.get('status')
            if map_status != 'completed' or recovery.get('missing_ranges') or recovery.get('retry_pending_ranges'):
                return {'status': 'incomplete_recovery_map', 'map_status': map_status,
                        'notes': 'Sparse/missing ranges cannot be interpreted as original zeros'}
        sha_a, sha_b = hashlib.sha256(), hashlib.sha256()
        first_mismatch = None
        mismatched_chunks = 0
        size = before_a.st_size
        step = chunk_mib * 1024 * 1024
        for offset in range(0, size, step):
            n = min(step, size - offset)
            left, right = a.read_at(offset, n), b.read_at(offset, n)
            if len(left) != n or len(right) != n:
                return {'status': 'read_error_or_short_read', 'offset': offset}
            sha_a.update(left)
            sha_b.update(right)
            if left != right:
                mismatched_chunks += 1
                if first_mismatch is None:
                    first_mismatch = offset + next(i for i, (x, y) in enumerate(zip(left, right)) if x != y)
        after_a, after_b = os.fstat(a.fd), os.fstat(b.fd)
        for before, after in [(before_a, after_a), (before_b, after_b)]:
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                return {'status': 'image_changed_during_verification'}
        return {
            'status': 'verified_byte_exact' if mismatched_chunks == 0 else 'data_mismatch',
            'source_sha256': sha_a.hexdigest(), 'candidate_sha256': sha_b.hexdigest(),
            'size_bytes': size, 'first_mismatch_offset': first_mismatch,
            'mismatched_chunks': mismatched_chunks, 'map_status': map_status,
            'notes': 'Byte equality against this stable file only; not proof of physical health or original correctness.'
        }
    finally:
        a.close()
        b.close()
