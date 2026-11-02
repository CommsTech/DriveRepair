"""Conservative plan for scan-driven, explicitly approved sector refresh.

This *does not* reconstruct corrupt file bytes. Isolated media read errors
trigger bounded read-only investigation before any write decision. Only verified,
consistently readable candidates may enter the journaled rewrite engine. Unknown
bytes and transport/identity failures never become authorized writes.
"""
from __future__ import annotations

import math
import errno
from collections import deque

from .health import media_from_smart, transport_from_smart


def tuned_scan(*, size: int, sector: int, mode: str, bus: str = "") -> dict:
    """Deterministic bounded-memory defaults; performance claims need hardware tests."""
    if mode not in {"quick", "full"} or size <= 0 or sector <= 0:
        raise ValueError("Invalid assisted scan request")
    # Large disks need larger sequential reads, not millions of progress events.
    chunk = 4 * 1024 * 1024 if mode == "full" and size >= 512 * 1024**3 else 1024 * 1024
    chunk = max(sector, (chunk + sector - 1) // sector * sector)
    samples = 256 if size >= 1024**4 else 128
    if mode == "quick" and bus.lower() in {"usb", "7", "12", "firewire"}:
        samples = min(samples, 128)  # avoid exhausting marginal USB docks
    return {"mode": "triage" if mode == "quick" else "full",
            "chunk": chunk, "samples": samples, "max_errors": 16}


def investigate_failed_ranges(reader, ranges: list[dict], *, sector: int,
                              max_reads: int = 96, max_regions: int = 16,
                              progress=None) -> dict:
    """Try to re-read error chunks, splitting down to logical sectors.

    Every candidate must match in TWO reads. This establishes repeatability,
    NOT the original/correct bytes. On a real drive this is deliberately bounded
    to avoid hammering failing media. Does not perform ANY writes.
    """
    if sector <= 0 or max_reads < 2 or max_regions < 1:
        raise ValueError('Invalid retry budget or sector size')
    pending = deque()
    for raw in ranges[:max_regions]:
        off, length = raw.get('offset'), raw.get('length')
        if type(off) is not int or type(length) is not int or off < 0 or length < sector or off % sector or length % sector:
            continue
        pending.append((off, length))
    consistent: list[dict] = []
    unresolved: list[dict] = []
    reads = 0
    device_unstable = False
    while pending and reads + 2 <= max_reads:
        off, length = pending.popleft()
        good = False
        try:
            one = reader.read_at(off, length)
            reads += 1
            if len(one) == length:
                two = reader.read_at(off, length)
                reads += 1
                good = len(two) == length and one == two
        except OSError as exc:
            # WinError 1117 is ERROR_IO_DEVICE, and Python may report errno=22.
            # The Win32 code takes precedence over the generic errno.
            # An inaccessible/disconnected drive is NOT a recoverable bad sector.
            # Do not turn further reads into a candidate after the identity or
            # transport becomes uncertain.
            if (getattr(exc, 'winerror', None) in {5, 6, 21, 1167} or
                    (getattr(exc, 'winerror', None) is None and exc.errno in {
                        errno.ENODEV, errno.ENXIO, errno.EBADF, errno.EACCES,
                        errno.EPERM, errno.ENOENT, errno.EINVAL})):
                device_unstable = True
                unresolved.append({'offset': off, 'length': length})
                break
        if good:
            consistent.append({'offset': off, 'length': length,
                               'classification': 'repeatable_after_read_error_not_checksum_verified'})
        elif length > sector:
            # Sector-aligned binary bisection, with no unbounded recursion.
            left = ((length // sector) // 2) * sector
            if left:
                pending.appendleft((off + left, length - left))
                pending.appendleft((off, left))
            else:
                unresolved.append({'offset': off, 'length': length})
        else:
            unresolved.append({'offset': off, 'length': length})
        if progress is not None:
            progress({'read_calls': reads, 'resolved_regions': len(consistent),
                      'unresolved_regions': len(unresolved), 'pending_regions': len(pending),
                      'offset': off})
    unresolved.extend({'offset': a, 'length': b} for a, b in pending)
    # Input may be truncated at the budget. Never imply all source errors resolved.
    limited = len(ranges) > max_regions or bool(pending)
    return {'consistent_regions': consistent, 'unresolved_regions': unresolved,
            'read_calls': reads, 'budget_exhausted': limited,
            'device_unstable': device_unstable,
            'uninvestigated_original_ranges': max(0, len(ranges) - max_regions)}


def plan_targeted_refresh(scan: dict, *, sector: int, chunk: int,
                          max_regions: int = 64, smart: dict | None = None,
                          hardware: bool = False, allow_unknown_health: bool = False,
                          allow_media_warning: bool = False,
                          policy: str = 'balanced') -> dict:
    """Return a bounded candidate set or a fail-closed explanation. Never a write permit."""
    reasons: list[str] = []
    if policy not in {'preserve', 'balanced'}:
        raise ValueError('Unknown guided repair policy')
    valid_statuses = {'completed', 'completed_with_slow_regions', 'completed_with_read_errors',
                      'aborted_error_limit'}
    # Hitting the read-error budget stops further scanning to protect the disk.
    # It is not itself a connection failure, nor does it invalidate separately
    # confirmed, repeatably readable candidates. All UNVISITED extents stay unknown.
    scan_incomplete = scan.get('status') == 'aborted_error_limit'
    if scan.get('status') not in valid_statuses:
        reasons.append('Drive/access failure or unsafe scan interruption; no write authorized')
    # Read failures are NOT a global write veto. They remain quarantined and
    # cannot be scheduled unless bounded read-only investigation recovered TWO
    # identical reads and the rewrite engine independently checks again.
    # Disagreement/extra-read failure quarantines the affected range, not
    # unrelated regions. If it has NO known offset, fail closed.
    if (scan.get('repeat_probe_failures') and
            not scan.get('repeat_probe_failed_ranges')):
        reasons.append('Failed repeat reads without offsets: cannot quarantine unstable data')
    if any(type(x.get('offset')) is not int or type(x.get('length')) is not int
           for x in (scan.get('inconsistent_reads') or [])):
        reasons.append('Unstable reads without usable offsets: cannot isolate suspect data')
    if scan.get("mode") not in {"triage", "full"}:
        reasons.append("Assisted repair requires triage or full scan")
    if scan.get('read_error_ranges_truncated'):
        reasons.append('Error map truncated; inspect the full result before writes')
    # A truncated slow-region map is not grounds to rewrite unknown bytes.
    # But independently observed candidate regions may still be treated in a
    # bounded subset, explicitly reported as PARTIAL maintenance.
    if not 1 <= max_regions <= 256:
        raise ValueError("Region budget must be 1–256")
    if hardware:
        medium = media_from_smart(smart)
        transport = transport_from_smart(smart)
        if medium == 'FAIL':
            reasons.append('Critical media health: stop writes and recommend replacement/rescue')
        elif medium == 'WARN' and not allow_media_warning:
            reasons.append('SMART media warning: requires explicit risk acknowledgement')
        if transport in {'WARN', 'FAIL'}:
            reasons.append('Transport/USB errors: stabilize the connection before writes')
        # Windows coarse health without SMART attributes is not evidence of a
        # healthy disk, particularly through an external USB bridge.
        if smart and smart.get("source") == "windows_storage_healthstatus":
            medium = "UNKNOWN"
        if medium == "UNKNOWN" and not allow_unknown_health:
            reasons.append("SMART health unavailable; requires separate unknown-health acknowledgment")
        if smart:
            temp = smart.get("temperature_c")
            if type(temp) in {int, float} and temp >= 55:
                reasons.append("Drive temperature is high; cool/stabilize before write maintenance")
            nvme = smart.get("nvme") or {}
            if type(nvme.get("percentage_used")) is int and nvme["percentage_used"] >= 100:
                reasons.append("NVMe reported endurance exhausted; replace instead of refreshing")
    if reasons:
        return {"status": "blocked", "reasons": reasons, "targets": [], "candidate_count": 0}
    size = int(scan["device_size_bytes"])
    regions = []
    original_errors = scan.get('read_error_ranges') or []
    unstable_ranges = (scan.get('inconsistent_reads') or []) + (scan.get('repeat_probe_failed_ranges') or [])
    if int(scan.get('read_error_chunks') or 0) and not original_errors:
        return {'status': 'blocked', 'reasons': [
            'Scan reported read errors without offsets; cannot quarantine affected data'],
            'targets': [], 'candidate_count': 0, 'unresolved_data': True}
    def overlaps(off, length, error_ranges):
        return any(type(e.get('offset')) is int and type(e.get('length')) is int and
                   off < e['offset'] + e['length'] and e['offset'] < off + length
                   for e in error_ranges)
    for raw in scan.get("slow_regions") or []:
        off = raw.get("offset")
        if type(off) is not int or off < 0 or off >= size or off % sector:
            continue
        length = min(chunk, size - off)
        length -= length % sector
        if not length:
            continue
        if raw.get("latency_ms") is None or not math.isfinite(float(raw["latency_ms"])):
            continue
        # Never treat an error-bearing parent chunk as reliable simply because
        # it also had slow reads. Follow-up subranges are handled separately.
        if not overlaps(off, length, original_errors + unstable_ranges):
            regions.append((off, length))
    investigation = scan.get('error_investigation') or {}
    if investigation.get('device_unstable'):
        return {'status': 'blocked', 'reasons': [
            'Drive lost access during bounded retries; stabilize the transport and re-identify the device'],
            'targets': [], 'candidate_count': 0, 'unresolved_data': True}
    if policy == 'balanced':
        for raw in investigation.get('consistent_regions') or []:
            off, length = raw.get('offset'), raw.get('length')
            if (type(off) is int and type(length) is int and off >= 0 and length >= sector
                    and off + length <= size and off % sector == 0 and length % sector == 0
                    and not overlaps(off, length, unstable_ranges)):
                regions.append((off, length))
    regions = sorted(set(regions))
    if any(a[0] + a[1] > b[0] for a, b in zip(regions, regions[1:])):
        return {"status": "blocked", "reasons": ["Overlapping suspect regions"],
                "targets": [], "candidate_count": len(regions)}
    all_candidates_count = len(regions)
    # Incremental work: choose a bounded set, never silently rewrite an
    # unbounded number of regions after one scan. Remaining candidates need a
    # later explicitly authorized cycle and a new pre-write verification.
    limited_candidates = len(regions) > max_regions
    if limited_candidates:
        regions = regions[:max_regions]
    unresolved = (scan_incomplete or limited_candidates or bool(scan.get('slow_regions_truncated')) or
                  bool(scan.get('skipped_untested_ranges')) or bool(unstable_ranges) or
                  (bool(scan.get('read_error_chunks')) and (
                      not investigation or investigation.get('unresolved_regions') or
                      investigation.get('uninvestigated_original_ranges') or
                      investigation.get('budget_exhausted'))))
    if not regions and unresolved:
        return {'status': 'blocked', 'reasons': ['Unrecoverable/unknown error areas; rescue or separately authorized destructive reinitialization required'],
                'targets': [], 'candidate_count': 0, 'unresolved_data': True}
    return {
        'scan_incomplete': scan_incomplete,
        'scanned_bytes': int(scan.get('attempted_bytes') or 0),
        "status": "partial_candidates_with_unresolved_data" if regions and unresolved else
                  "candidates_found" if regions else "no_candidates",
        "reasons": [], "targets": regions, "candidate_count": len(regions),
        "remaining_candidate_count": all_candidates_count - len(regions),
        "incremental_batch": limited_candidates,
        "unresolved_data": bool(unresolved),
        "notes": ("Rewritten candidates are repeatably readable, NOT bit-perfect by proof. "
                  "Unknown/unreadable regions are EXCLUDED. The write engine rereads "
                  "the bytes, journals them, rewrites and verifies; no replacement bytes "
                  "are manufactured. Unresolved data requires separate rescue or explicit "
                  "destructive sector reinitialization, not automatic overwrites."),
    }
