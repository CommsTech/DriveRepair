"""Bounded, read-only investigation of a previously failing region.

No rewriting, firmware commands, or unbounded retry loops. A 4 MiB request
rejected by the OS is not evidence that a 4 MiB physical area is defective.
"""
from __future__ import annotations
from typing import Any

import errno
import hashlib


def probe_range(reader, *, offset: int, length: int, sector: int,
                size: int, max_reads: int = 32) -> dict:
    if (sector not in {512, 1024, 2048, 4096, 8192} or offset < 0 or length < sector or
            offset % sector or length % sector or offset + length > size or
            length > 8 * 1024 * 1024 or not 1 <= max_reads <= 64):
        raise ValueError('Invalid bounded, sector-aligned probe range')
    work = [(offset, length)]
    results: list[dict[str, Any]] = []
    calls = 0
    total_bytes = 0
    while work and calls < max_reads:
        at, count = work.pop(0)
        calls += 1
        total_bytes += count
        try:
            data = reader.read_at(at, count)
            if len(data) != count:
                raise OSError(errno.EIO, f'short read: {len(data)} / {count}')
            results.append({'offset': at, 'length': count, 'result': 'readable',
                            'sha256_observed': hashlib.sha256(data).hexdigest()})
        except OSError as exc:
            winerror = getattr(exc, 'winerror', None)
            error = {'offset': at, 'length': count,
                     'result': 'read_request_failed', 'errno': exc.errno,
                     'winerror': winerror}
            results.append(error)
            # An OS invalid-parameter error (errno=22 / WinError=87) frequently
            # means a rejected request, not defective media. Try smaller requests,
            # but never infer the original data from them.
            if count > sector and winerror not in (5, 6, 21, 1117):
                half = ((count // 2) // sector) * sector
                if 0 < half < count:
                    work.extend([(at, half), (at + half, count - half)])
            # Access denied, invalid handle, device-not-ready and I/O device
            # errors require separate host/transport diagnostics, not retries.
    known_bytes = sum(int(r['length']) for r in results if r['result'] == 'readable')
    unresolved = [r for r in results if r['result'] == 'read_request_failed']
    return {
        'operation': 'bounded_readonly_region_probe',
        'source_offset': offset, 'region_bytes': length, 'reads_attempted': calls,
        'read_bytes_requested': total_bytes, 'readable_request_bytes': known_bytes,
        'attempt_history': results,
        'unresolved_read_requests': len(unresolved),
        'remaining_queued_ranges': len(work),
        'status': 'investigation_required' if unresolved or work else 'all_requests_readable',
        'notes': 'A failed large request followed by successful smaller requests suggests a possible '
                 'request-size/controller/bridge issue, not proof of a defective sector. '
                 'Read success does not establish original bit correctness. No bytes written.',
    }
