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


def tuned_scan(*, size: int, sector: int, mode: str, bus: str = "",
               model: str = "", media_type: str = "", recording: str = "") -> dict:
    """Media-aware read settings; quick mode samples >=10% of the disk.

    The quick scan intentionally takes meaningful time on multi-TB devices:
    sampling 10% of a 12 TB drive is ~1.2 TB of I/O. This is NOT a 2-second
    screening test. Historical problem regions are additional read-only hints.
    """
    from .media_profiles import identify_profile, quick_coverage_plan
    if mode not in {'quick', 'full'} or size <= 0 or sector <= 0 or size % sector:
        raise ValueError('Invalid assisted scan request')
    profile = identify_profile(model=model, bus=bus, media_type=media_type,
                               recording=recording, sector=sector)
    if mode == 'quick':
        quick_chunk = profile.quick_chunk
        # Bound the progress queue for multi-TB scans without accepting a
        # smaller-than-requested percentage. An expensive 10% read is honest.
        while quick_coverage_plan(size, quick_chunk)['samples'] > 100000:
            quick_chunk *= 2
        plan = quick_coverage_plan(size, quick_chunk)
        return {'mode': 'triage', 'chunk': quick_chunk,
                'samples': plan['samples'], 'max_errors': 10000,
                'requested_coverage_pct': 10.0, 'profile': profile.kind,
                'profile_evidence': profile.evidence, 'media_note': profile.maintenance_note}
    return {'mode': 'full', 'chunk': profile.full_start_chunk, 'samples': 128,
            'max_errors': 10000, 'max_chunk': profile.full_max_chunk,
            'min_chunk': profile.read_min_chunk, 'profile': profile.kind,
            'profile_evidence': profile.evidence, 'media_note': profile.maintenance_note}


def investigate_failed_ranges(reader, ranges: list[dict], *, sector: int,
                              max_reads: int = 96, max_regions: int = 16,
                              progress=None, max_elapsed_seconds: float = 20.0) -> dict:
    """Try to re-read error chunks, splitting down to logical sectors.

    Every candidate must match in TWO reads. This establishes repeatability,
    NOT the original/correct bytes. On a real drive this is deliberately bounded
    to avoid hammering failing media. Does not perform ANY writes.
    """
    import time
    if sector <= 0 or max_reads < 2 or max_regions < 1 or max_elapsed_seconds <= 0:
        raise ValueError('Invalid retry budget or sector size')
    started = time.monotonic()
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
    while pending and reads < max_reads and time.monotonic() - started < max_elapsed_seconds:
        off, length = pending.popleft()
        good = False
        try:
            # Charge BEFORE the call: a failed OS/USB read costs a real I/O
            # operation, sometimes many seconds. Never allow recursive splits
            # to evade the user's retry budget.
            reads += 1
            if progress is not None:
                progress({'read_calls': reads, 'max_reads': max_reads,
                          'offset': off, 'length': length, 'state': 'reading',
                          'elapsed_seconds': time.monotonic() - started})
            one = reader.read_at(off, length)
            if len(one) == length and reads < max_reads and time.monotonic() - started < max_elapsed_seconds:
                reads += 1
                two = reader.read_at(off, length)
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
            progress({'read_calls': reads, 'max_reads': max_reads,
                      'resolved_regions': len(consistent),
                      'unresolved_regions': len(unresolved), 'pending_regions': len(pending),
                      'elapsed_seconds': time.monotonic() - started,
                      'offset': off, 'length': length, 'state': 'probed'})
    unresolved.extend({'offset': a, 'length': b} for a, b in pending)
    # Input may be truncated at the budget. Never imply all source errors resolved.
    limited = len(ranges) > max_regions or bool(pending)
    return {'max_reads': max_reads, 'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out_soft': bool(pending and time.monotonic() - started >= max_elapsed_seconds),
            'consistent_regions': consistent, 'unresolved_regions': unresolved,
            'read_calls': reads, 'budget_exhausted': limited,
            'device_unstable': device_unstable,
            'uninvestigated_original_ranges': max(0, len(ranges) - max_regions)}



def inspect_failed_boundaries(reader, ranges: list[dict], *, size: int,
                              sector: int, probe_bytes: int = 64 * 1024,
                              max_probes: int = 24,
                              max_elapsed_seconds: float = 15.0,
                              progress=None) -> dict:
    """Bounded read-only investigation OUTSIDE both edges of failed requests.

    A failed 16 MiB read identifies an UNKNOWN 16 MiB range, not a bad sector.
    Probe success identifies the nearest *observed* readable logical range,
    not a physical NAND page or platter track. Never authorize a write here.
    Limits are soft: OS/USB firmware can stall an individual synchronous read.
    """
    import time
    from .adaptive_scan import classify_error

    if not 0 < sector <= 1024 * 1024 or size <= 0 or size % sector:
        raise ValueError('Invalid disk geometry')
    if max_probes < 2 or max_probes > 256 or max_elapsed_seconds <= 0:
        raise ValueError('Invalid inspection budget')
    span = max(sector, probe_bytes // sector * sector)
    deadline = time.monotonic() + max_elapsed_seconds
    probes = 0
    observations = []
    regions = []
    for raw in ranges[:8]:
        off, length = raw.get('offset'), raw.get('length')
        if (type(off) is not int or type(length) is not int or off < 0 or
                length < sector or length % sector or off % sector or off + length > size):
            continue
        neighbors = {}
        for side in ('left', 'right'):
            boundary = off if side == 'left' else off + length
            found = None
            for step in range(4):
                if probes + 2 > max_probes or time.monotonic() >= deadline:
                    found = {'status': 'budget_exhausted'}
                    break
                distance = span * (2 ** step)
                if side == 'left':
                    start = max(0, boundary - distance)
                    end = min(boundary, start + span)
                else:
                    start = min(size, boundary + (distance - span))
                    end = min(size, start + span)
                start = start // sector * sector
                end = end // sector * sector
                length_to_read = end - start
                if length_to_read < sector:
                    found = {'status': 'drive_boundary'}
                    break
                try:
                    a = reader.read_at(start, length_to_read)
                    probes += 1
                    if len(a) != length_to_read:
                        raise OSError('short read')
                    b = reader.read_at(start, length_to_read)
                    probes += 1
                    if len(b) != length_to_read or a != b:
                        observation = 'inconsistent'
                    else:
                        observation = 'repeatable_read'
                except OSError as exc:
                    probes += 1  # charge the attempted operation
                    observation = classify_error(exc)
                    if observation == 'device_or_access_unavailable':
                        found = {'status': 'device_unavailable'}
                entry = {'offset': start, 'length': length_to_read,
                         'side': side, 'observation': observation}
                observations.append(entry)
                if progress is not None:
                    progress({'probes': probes, **entry})
                if observation == 'repeatable_read':
                    found = {'status': 'boundary_observed', 'offset': start,
                             'length': length_to_read}
                    break
                if found and found['status'] == 'device_unavailable':
                    break
            neighbors[side] = found or {'status': 'not_established'}
        regions.append({'offset': off, 'length': length, 'neighbors': neighbors})
        if any(x.get('status') == 'device_unavailable' for x in neighbors.values()):
            break
    return {'regions': regions, 'observations': observations, 'read_calls': probes,
            'budget_exhausted': (probes >= max_probes or time.monotonic() >= deadline or
                                 any(side.get('status') == 'budget_exhausted'
                                     for r in regions for side in r['neighbors'].values())),
            'no_writes': True, 'repair_authorized': False,
            'note': 'Logical neighbors only; readable boundary is not a good-sector or file-integrity certificate.'}

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


def inspect_adjacent_regions(reader, *, size: int, sector: int,
                             targets: list[tuple[int, int]],
                             excluded: list[dict] | None = None,
                             window: int = 256 * 1024,
                             max_reads: int = 64) -> dict:
    """Read BOTH sides of verified target regions; no source writes.

    Adjoining LBAs are not necessarily physically adjacent tracks, especially
    through SMR translation layers, SSD FTLs or USB bridge mappings. Returning
    a consistent read is NOT proof of original data correctness. Only callers
    with separately authorized CMR maintenance may add these to a write plan.
    """
    if size <= 0 or sector <= 0 or size % sector or window < sector or max_reads < 2:
        raise ValueError('Invalid neighbor inspection budget')
    window = (window // sector) * sector
    forbidden = excluded or []
    probes = []
    for off, length in targets:
        for neighbor, nlen in ((max(0, off - window), min(window, off)),
                               (off + length, min(window, max(0, size - off - length)))):
            if (nlen < sector or neighbor % sector or
                    any(neighbor < t_off + t_len and t_off < neighbor + nlen
                        for t_off, t_len in targets) or
                    any(isinstance(r, dict) and type(r.get('offset')) is int and
                        type(r.get('length')) is int and
                        neighbor < r['offset'] + r['length'] and
                        r['offset'] < neighbor + nlen for r in forbidden)):
                continue
            probes.append((neighbor, nlen))
    good, rejected, seen = [], [], set()
    calls = 0
    for off, length in probes:
        if (off, length) in seen:
            continue
        seen.add((off, length))
        if calls + 2 > max_reads:
            rejected.append({'offset': off, 'length': length, 'reason': 'budget_exhausted'})
            continue
        try:
            a = reader.read_at(off, length)
            b = reader.read_at(off, length)
            calls += 2
            if len(a) != length or a != b:
                rejected.append({'offset': off, 'length': length, 'reason': 'not_repeatable'})
            else:
                good.append((off, length))
        except OSError as exc:
            calls += 2   # Conservative budget charge; may have done just one.
            from .adaptive_scan import classify_error
            rejected.append({'offset': off, 'length': length, 'reason': 'io_error',
                             'classification': classify_error(exc)})
    return {'consistent_neighbors': sorted(set(good)), 'rejected_neighbors': rejected,
            'read_budget_used': calls, 'no_writes': True,
            'original_bytes_proven_correct': False}
