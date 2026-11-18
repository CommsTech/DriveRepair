"""Independent *post-close* content comparison for journaled targeted rewrites.

A completed write/readback while an exclusive RW handle is open does not prove
later readability. This reopens the patient through a READ-ONLY handle, reads
committed regions twice, and compares SHA-256 against saved prewrite hashes.
No actual filesystem-data provenance is inferred from a matching digest.
"""
from __future__ import annotations

import hashlib


def verify_committed_regions(reader, records: list, *, size: int, sector: int,
                             max_regions: int = 256, max_bytes: int = 256 * 1024 * 1024) -> dict:
    """Fail closed on corrupt metadata, partial reads, read errors, or different bytes."""
    if not (0 < sector <= 65536 and size > 0 and size % sector == 0):
        raise ValueError('Invalid patient size or sector alignment')
    if not (1 <= len(records) <= max_regions):
        raise ValueError('Postverification needs 1–256 committed region digests')
    verified = 0
    previous_end = 0
    failures = []
    for entry in records:
        if (not isinstance(entry, list) or len(entry) != 3 or
                type(entry[0]) is not int or type(entry[1]) is not int or
                not isinstance(entry[2], str)):
            raise ValueError('Malformed committed digest record')
        offset, length, digest = entry
        if (offset < previous_end or offset < 0 or length <= 0 or
                offset % sector or length % sector or offset + length > size or
                length > 16 * 1024 * 1024 or
                len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)):
            raise ValueError('Invalid committed digest span or SHA-256')
        if verified + length > max_bytes:
            raise ValueError('Postverification byte budget exceeded')
        previous_end = offset + length
        try:
            first = reader.read_at(offset, length)
            second = reader.read_at(offset, length)
        except (OSError, RuntimeError) as exc:
            failures.append({'offset': offset, 'length': length,
                             'classification': 'read_error', 'error_type': type(exc).__name__})
            continue
        if len(first) != length or len(second) != length:
            failures.append({'offset': offset, 'length': length,
                             'classification': 'short_read'})
        elif first != second:
            failures.append({'offset': offset, 'length': length,
                             'classification': 'inconsistent_readback'})
        elif hashlib.sha256(first).hexdigest() != digest:
            failures.append({'offset': offset, 'length': length,
                             'classification': 'preimage_digest_mismatch'})
        else:
            verified += length
    return {
        'status': 'postverify_passed' if not failures else 'postverify_failed',
        'verified_bytes': verified,
        'recorded_regions': len(records),
        'failures': failures,
        'checks': 'two independent reads plus SHA-256 equality with prewrite snapshot',
        'no_writes': True,
        'notes': 'Passing confirms currently readable rewritten bytes match the prewrite data; '
                 'it does not certify all sectors, file integrity, or future reliability.',
    }
