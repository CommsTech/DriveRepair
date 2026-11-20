"""Adaptive, bounded-memory first pass for READ-ONLY full-surface analysis.

Good areas are read sequentially in larger requests. Failed/slow areas are
recorded and investigated *after* the first pass, to avoid head thrashing on
failing disks. No reads prove bit correctness and this module NEVER writes.
"""
from __future__ import annotations

import errno
import math
import statistics
import time
from collections import deque
from typing import Any, Callable


# Win32 ERROR_IO_DEVICE (1117) can surface as Python errno EINVAL (22).
# ERRNO 22 is only fatal without the more specific native error code.
DEVICE_IO_ERRORS = {1117, 23, 1110}
FATAL_WINERRORS = {5, 6, 21, 433, 1167}
FATAL_ERRNOS = {errno.ENODEV, errno.ENXIO, errno.EBADF, errno.EACCES,
                errno.EPERM, errno.ENOENT}


def classify_error(exc: OSError) -> str:
    winerror = getattr(exc, 'winerror', None)
    if winerror in FATAL_WINERRORS:
        return 'device_or_access_unavailable'
    if winerror in DEVICE_IO_ERRORS:
        return 'io_device_error_unconfirmed_media'
    if exc.errno in FATAL_ERRNOS:
        return 'device_or_access_unavailable'
    if exc.errno == errno.EINVAL:
        return 'invalid_read_request'
    return 'read_failure_unconfirmed_media'


def adaptive_full_scan(reader, *, size: int, sector: int, chunk: int,
                       max_errors: int = 16, progress: Callable | None = None,
                       max_deferred: int = 256, max_followup_reads: int = 96,
                       min_chunk: int | None = None, max_chunk: int | None = None,
                       known_suspects: list[dict] | None = None,
                       resume_state: dict | None = None, checkpoint=None) -> dict:
    """One full-surface pass, skipping isolated failures then bounded refinement.

    The returned `read_error_ranges` are original failed I/O requests, even if
    smaller reads later succeed. Only known-good repeatable subranges are sent
    to the separate repair planner; the original failure is not erased.
    """
    if size <= 0 or sector < 1 or size % sector or chunk < sector or chunk % sector:
        raise ValueError('Invalid size or alignment')
    if not 1 <= max_errors <= 10000 or not 1 <= max_deferred <= 10000:
        raise ValueError('Invalid failure budgets')
    min_chunk = max(sector, (min_chunk or max(256 * 1024, sector)))
    min_chunk = (min_chunk + sector - 1) // sector * sector
    max_chunk = min(16 * 1024 * 1024, max_chunk or max(chunk, 8 * 1024 * 1024))
    max_chunk = max(sector, max_chunk // sector * sector)
    chunk = min(max_chunk, max(min_chunk, chunk))
    started = time.monotonic()
    checked = readable = read_count = failures = 0
    prior = resume_state or {}
    position = int(prior.get('position', 0))
    if position < 0 or position > size or position % sector:
        raise ValueError('Invalid resume position')
    checked = int(prior.get('checked', 0))
    readable = int(prior.get('readable', 0))
    read_count = int(prior.get('read_count', 0))
    failures = int(prior.get('failures', 0))
    deferred: list[dict] = [dict(x) for x in prior.get('deferred', [])]
    suspect = [dict(x) for x in (known_suspects or [])[:128]
               if type(x) is dict and type(x.get('offset')) is int and
               0 <= x['offset'] < size]
    slow: list[dict] = [dict(x) for x in prior.get('slow', [])]
    slow_count = int(prior.get('slow_count', len(slow)))
    read_sizes = set()
    adjustments = 0
    size_now = int(prior.get('size_now', chunk))
    if not min_chunk <= size_now <= max_chunk or size_now % sector:
        size_now = chunk
    recent_rate: deque[float] = deque(maxlen=32)
    consecutive_errors = 0
    healthy_streak = 0
    skipped: list[dict] = [dict(x) for x in prior.get('skipped', [])]
    status = 'completed'
    error_count_over_limit = False
    retries_limited = False
    latency_window: deque[float] = deque(maxlen=256)
    checkpoint_min_interval = 2.0
    last_checkpoint_at = 0.0

    def write_checkpoint(*, force=False):
        nonlocal last_checkpoint_at
        if checkpoint is None:
            return
        now = time.monotonic()
        # A durable checkpoint costs a temp file, two fsyncs and a rename.
        # Writing one after every chunk added minutes of pure overhead on slow
        # media for a position that a crash can only lose by seconds. Forced
        # saves (abort, status change, completion) still happen immediately.
        if not force and now - last_checkpoint_at < checkpoint_min_interval:
            return
        checkpoint({'position': position, 'checked': checked,
                    'readable': readable, 'read_count': read_count,
                    'failures': failures, 'deferred': deferred[:256],
                    'slow': slow[:1024], 'slow_count': slow_count,
                    'skipped': skipped[:256], 'size_now': size_now}, force=force)
        last_checkpoint_at = now

    def report(off, length, elapsed_ms, error=None, category=None):
        if progress is None:
            return
        elapsed = max(0.001, time.monotonic() - started)
        progress(min(size, off + length), size, {
            'offset': off, 'length': length,
            'attempted_bytes': checked, 'readable_bytes': readable,
            'read_error_chunks': failures, 'failed': error is not None,
            'error_class': category, 'deferred_regions': len(deferred),
            'read_size_bytes': size_now, 'scan_position_bytes': min(size, off + length),
            'latency_ms': elapsed_ms,
            'median_ms': statistics.median(latency_window) if latency_window else None,
            'speed_bps': readable / elapsed,
        })

    # Favor preserving good areas on the first pass. No immediate shrinking down
    # to a sector after a bad read (that can trap an aging head on bad media).
    while position < size:
        length = min(size_now, size - position)
        # All sizes, including the tail, are sector aligned.
        length -= length % sector
        if length < sector:
            raise RuntimeError('Alignment bug in adaptive scan')
        read_sizes.add(length)
        read_count += 1
        checked += length
        t0 = time.monotonic()
        issue = None
        category = None
        try:
            payload = reader.read_at(position, length)
            if len(payload) != length:
                issue = f'short read ({len(payload)}/{length})'
                category = 'short_read'
        except OSError as exc:
            category = classify_error(exc)
            _winerror = getattr(exc, 'winerror', None)
            issue = (f'{type(exc).__name__}: errno={exc.errno}' +
                     (f', winerror={_winerror}' if _winerror is not None else ''))
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        if issue:
            failures += 1
            consecutive_errors += 1
            healthy_streak = 0
            if len(deferred) < max_deferred:
                deferred.append({'offset': position, 'length': length,
                                 'error': issue, 'interpretation': category})
            else:
                error_count_over_limit = True
            if category in {'device_or_access_unavailable', 'invalid_read_request'}:
                status = 'aborted_device_or_access_error'
                report(position, length, elapsed_ms, issue, category)
                write_checkpoint(force=True)
                break
            if failures >= max_errors:
                retries_limited = True  # affects deferred probe budget, not whole-disk progress
            new_size = max(min_chunk, size_now // 2)
            new_size = max(sector, new_size // sector * sector)
            if new_size != size_now:
                size_now = new_size
                adjustments += 1
            report(position, length, elapsed_ms, issue, category)
            position += length
            write_checkpoint()
            # A large cluster of failed reads is bypassed, not repeatedly hit.
            # The skipped space is UNTESTED, never classified as healthy.
            if consecutive_errors >= 6 and position < size:
                skip = min(32 * 1024 * 1024, size - position)
                skip -= skip % sector
                if skip:
                    skipped.append({'offset': position, 'length': skip, 'reason': 'repeated_io_failures'})
                    position += skip
                    write_checkpoint(force=True)
                    consecutive_errors = 0
                    report(position - skip, skip, 0.0, 'skipped untested after repeated I/O errors',
                           'skipped_untested')
            continue
        readable += length
        consecutive_errors = 0
        healthy_streak += 1
        latency_window.append(elapsed_ms)
        rate = length / max(elapsed_ms / 1000.0, 0.001)
        recent_rate.append(rate)
        # Normalize latency by bytes read; don't label an 8 MiB read slow just
        # because it takes longer than a 1 MiB read.
        per_mib = elapsed_ms * (1024 * 1024) / length
        baseline = statistics.median(latency_window) * (1024 * 1024) / max(size_now, sector)
        if per_mib > max(100.0, 4 * baseline):
            slow_count += 1
            if len(slow) < 1024:
                slow.append({'offset': position, 'length': length,
                             'latency_ms': round(elapsed_ms, 3),
                             'median_ms': round(baseline * length / (1024 * 1024), 3)})
            # Small, local follow-ups belong in subsequent stage, not now.
            if len(suspect) < 128:
                suspect.append({'offset': position, 'length': length, 'reason': 'high_latency'})
            healthy_streak = 0
        elif healthy_streak >= 12 and size_now < max_chunk:
            new_size = min(max_chunk, size_now * 2)
            new_size -= new_size % sector
            if new_size != size_now:
                size_now = new_size
                adjustments += 1
            healthy_streak = 0
        report(position, length, elapsed_ms)
        position += length
        write_checkpoint()

    write_checkpoint(force=True)
    if status == 'completed' and (deferred or skipped or error_count_over_limit):
        status = 'completed_with_read_errors'
    elif status == 'completed' and slow:
        status = 'completed_with_slow_regions'
    investigation = None
    if deferred and status != 'aborted_device_or_access_error':
        # Import lazily to avoid making the scanner depend on refresh internals.
        from .guided_repair import investigate_failed_ranges
        investigation = investigate_failed_ranges(
            reader, deferred, sector=sector,
            max_reads=min(max_followup_reads, 24), max_regions=min(8, max_deferred))
        if investigation.get('device_unstable'):
            status = 'aborted_device_or_access_error'

    boundary_investigation = None
    if deferred and status != 'aborted_device_or_access_error':
        from .guided_repair import inspect_failed_boundaries
        boundary_investigation = inspect_failed_boundaries(
            reader, deferred[:8], size=size, sector=sector,
            probe_bytes=max(sector, min(64 * 1024, min_chunk)),
            max_probes=16, max_elapsed_seconds=12.0)
    elapsed = max(0.001, time.monotonic() - started)
    # Fast pass never interprets skipped extents as covered or good.
    visited = max(0, position - sum(int(x['length']) for x in skipped))
    result = {
        'status': status, 'mode': 'full', 'adaptive_io': True,
        'device_size_bytes': size, 'logical_sector_bytes': sector,
        'readable_bytes': readable, 'attempted_bytes': checked,
        'attempted_chunks': read_count,
        'planned_chunks': math.ceil(size / chunk),
        'read_error_chunks': failures, 'read_error_ranges': deferred,
        'error_boundary_investigation': boundary_investigation,
        'read_error_ranges_truncated': error_count_over_limit,
        'deferred_retry_budget_reached': retries_limited,
        'slow_regions': slow, 'slow_region_count': slow_count,
        'slow_regions_truncated': slow_count > len(slow),
        'inconsistent_reads': [], 'repeat_probe_failures': 0,
        'repeat_probe_failed_ranges': [], 'extra_suspect_reads': 0,
        'follow_up_chunks': 0,
        'surface_coverage_pct': round(100 * min(size, visited) / size, 6),
        'elapsed_seconds': round(elapsed, 3),
        'resume_position_bytes': position,
        'resumed_from_bytes': int(prior.get('position', 0)),
        'read_sizes_bytes': sorted(read_sizes),
        'read_size_adjustments': adjustments,
        'skipped_untested_ranges': skipped,
        'known_suspects_considered': len(known_suspects or []),
        'follow_up_suspects': suspect,
        'notes': ('Adaptive sequential first pass; failed requests are NOT proof of damaged media. '
                  'Difficult regions are deferred to bounded smaller reads; skipped ranges remain UNKNOWN. '
                  'Readability and repeatability are NOT proof of bit correctness.'),
    }
    if investigation is not None:
        result['error_investigation'] = investigation
    return result


def calibrate_initial_read(reader, *, size: int, sector: int,
                           max_chunk: int = 16 * 1024 * 1024,
                           min_chunk: int = 1024 * 1024) -> dict:
    """Small, read-only transfer-size calibration; never a health certification.

    Tests increasing aligned reads in sequential locations, avoiding repeatedly
    reading one cached region. Returns the best *observed* good size; later
    full-scan scheduling still adapts as the drive's state changes. Stops on
    first failure to avoid hammering a suspected bad region.
    """
    if size <= 0 or sector <= 0 or size % sector:
        raise ValueError('Invalid device geometry')
    candidates = []
    c = max(sector, min_chunk // sector * sector)
    while c <= max_chunk:
        candidates.append(c)
        c *= 2
    readings: list[dict[str, Any]] = []
    at = 0
    for request in candidates[:5]:
        length = min(request, size - at)
        length -= length % sector
        if length <= 0:
            break
        t0 = time.monotonic()
        try:
            received = reader.read_at(at, length)
            if len(received) != length:
                raise OSError(errno.EIO, 'short calibration read')
        except OSError as exc:
            return {'chosen_chunk': _choose_calibrated(readings, min_chunk),
                    'measurements': readings, 'ended_on_error': True,
                    'error_class': classify_error(exc),
                    'extra_probe_bytes': at}
        seconds = max(time.monotonic() - t0, 0.000001)
        readings.append({'chunk': length, 'seconds': round(seconds, 6),
                         'bytes_per_second': round(length / seconds)})
        at += length
    return {'chosen_chunk': _choose_calibrated(readings, min_chunk),
            'measurements': readings, 'ended_on_error': False,
            'extra_probe_bytes': at}


def _choose_calibrated(records: list[dict], fallback: int) -> int:
    if not records:
        return fallback
    fastest = max(float(r['bytes_per_second']) for r in records)
    # Favor larger requests when their observed rate is within 95% of best,
    # reducing syscall overhead without chasing tiny timing fluctuations.
    return max(int(r['chunk']) for r in records
               if float(r['bytes_per_second']) >= fastest * .95)
