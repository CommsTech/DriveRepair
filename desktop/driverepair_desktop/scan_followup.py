"""Read-only follow-up from a completed scan; no repeat full-surface sweep.

Scan findings are hints, never write authority and never original data. A
repeatable read is not a checksum-verified recovered file or repaired medium.
"""
from __future__ import annotations

from .guided_repair import investigate_failed_ranges


def checked_ranges(scan: dict, device: dict, *, maximum: int = 32) -> list[dict]:
    if not isinstance(scan, dict) or not isinstance(device, dict):
        raise ValueError('Missing previous scan and current device identity')
    scanned = scan.get('device')
    if not isinstance(scanned, dict) or scanned.get('identity_hint') != device.get('identity_hint'):
        raise ValueError('Prior scan belongs to another device. No reads were started')
    size = int(device.get('size_bytes') or 0)
    sector = int(device.get('sector_size') or 0)
    if (size <= 0 or sector <= 0 or size % sector or
            scan.get('device_size_bytes') != size or scan.get('logical_sector_bytes') != sector):
        raise ValueError('Geometry changed since scan; cannot reuse suspect offsets')
    candidates = scan.get('read_error_ranges')
    if not isinstance(candidates, list) or len(candidates) > 4096 or not candidates:
        raise ValueError('No bounded failed ranges in the prior scan; do not invent repair targets')
    accepted: list[dict] = []
    for raw in candidates[:maximum]:
        if not isinstance(raw, dict):
            raise ValueError('Invalid prior scan range')
        off, length = raw.get('offset'), raw.get('length')
        if (type(off) is not int or type(length) is not int or off < 0 or length < sector or
                off % sector or length % sector or off + length > size):
            raise ValueError('Malformed or unaligned failed range')
        accepted.append({'offset': off, 'length': length})
    return accepted


def recheck_errors(scan: dict, device: dict, reader, *, max_reads: int = 96,
                   max_elapsed_seconds: float = 75.0) -> dict:
    ranges = checked_ranges(scan, device)
    info = investigate_failed_ranges(reader, ranges,
        sector=int(device['sector_size']), max_regions=len(ranges),
        max_reads=max_reads, max_elapsed_seconds=max_elapsed_seconds,
        max_probe_bytes=65536)
    unresolved = info['unresolved_regions']
    # Never use a success status for remediation: only a read-only follow-up.
    return {'status': 'read_only_suspect_recheck_completed',
            'device': {'identity_hint': device['identity_hint'], 'model': device.get('model')},
            'scan_regions_considered': len(ranges),
            'original_read_failures': scan.get('read_error_chunks'),
            'repeatably_readable_ranges': info['consistent_regions'],
            'unresolved_ranges': unresolved,
            'read_calls': info['read_calls'],
            'remaining_unchecked': bool(info.get('budget_exhausted')) or
                                   bool(scan.get('read_error_ranges_truncated')),
            'patient_writes': 0,
            'verified_files': 0,
            'message': 'Rechecked prior failed addresses without repeating the full scan. '
                       'No source sectors were repaired or written. To save data use Rescue to image; '
                       'repeatability does not prove original bytes.'}
