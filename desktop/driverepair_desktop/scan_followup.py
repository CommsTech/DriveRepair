"""Read-only follow-up from a completed scan; no repeat full-surface sweep.

Scan findings are hints, never write authority and never original data. A
repeatable read is not a checksum-verified recovered file or repaired medium.
"""
from __future__ import annotations

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
    if type(maximum) is not int or not 1 <= maximum <= 32:
        raise ValueError('Follow-up range limit must be between 1 and 32')
    candidates = scan.get('read_error_ranges')
    if not isinstance(candidates, list) or len(candidates) > 4096 or not candidates:
        raise ValueError('No bounded failed ranges in the prior scan; do not invent repair targets')
    accepted: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for raw in candidates:
        if not isinstance(raw, dict):
            raise ValueError('Invalid prior scan range')
        off, length = raw.get('offset'), raw.get('length')
        if (type(off) is not int or type(length) is not int or off < 0 or length < sector or
                off % sector or length % sector or off + length > size):
            raise ValueError('Malformed or unaligned failed range')
        key = (off, length)
        if key in seen:
            continue
        seen.add(key)
        accepted.append({'offset': off, 'length': length})
        if len(accepted) >= maximum:
            break
    return accepted


def recheck_errors(scan: dict, device: dict, reader, *, max_reads: int | None = None,
                   max_elapsed_seconds: float | None = None,
                   snapshot: dict | None = None,
                   aggressive: bool = False,
                   health_probe=None) -> dict:
    """Latency-prioritized read-only follow-up; never writes the patient."""
    from .weak_region_recovery import run_weak_region_pass

    # Preserve legacy callers that still expect the historical status string
    # while exposing the richer weak-region plan metadata.
    report = run_weak_region_pass(
        scan, device, reader,
        snapshot=snapshot,
        aggressive=aggressive,
        health_probe=health_probe,
        max_reads=max_reads,
        max_elapsed_seconds=max_elapsed_seconds,
    )
    report['status'] = 'read_only_suspect_recheck_completed'
    report['message'] = (
        'Rechecked prior failed addresses without repeating the full scan. '
        'No source sectors were repaired or written. To save data use Rescue to image; '
        'repeatability does not prove original bytes.')
    return report
