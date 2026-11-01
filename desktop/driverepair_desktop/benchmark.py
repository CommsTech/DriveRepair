"""Read-only, bounded-memory storage read benchmark and latency map.

A benchmark reflects current device/OS/cache conditions, not physical health.
Use repeatability, device health and pre/post comparisons for conclusions.
"""
from __future__ import annotations

import errno
import time

from .scanner import Reader, scan_offsets


def read_benchmark(reader: Reader, *, size: int, sector: int, mode: str = 'sample',
                   samples: int = 256, chunk: int = 1024 * 1024,
                   max_errors: int = 16, timer=time.perf_counter) -> dict:
    if (size <= 0 or sector <= 0 or size % sector or chunk < sector or
            chunk % sector or chunk > 16 * 1024 * 1024 or
            mode not in {'sample', 'full'} or not 1 <= samples <= 100000 or
            not 1 <= max_errors <= 1000):
        raise ValueError('Invalid benchmark parameters')
    latencies: list[float] = []
    planned = (size + chunk - 1) // chunk if mode == 'full' else min(samples, (size + chunk - 1) // chunk)
    stride = max(1, (planned + 8191) // 8192)
    count = 0
    zone_stats = [dict(samples=0, successful_bytes=0, slowest_ms=0.0,
                       read_errors=0) for _ in range(10)]
    ok_bytes = errors = requested = 0
    started = timer()
    stopped = 'completed'
    for offset, count_bytes in scan_offsets(size, chunk, mode, samples):
        count += 1
        zone = zone_stats[min(9, (10 * offset // size))]
        zone['samples'] += 1
        t = timer()
        try:
            got = reader.read_at(offset, count_bytes)
            duration_ms = (timer() - t) * 1000
            if len(got) != count_bytes:
                raise OSError(errno.EIO, 'Short read')
            if count % stride == 0 and len(latencies) < 8192:
                latencies.append(duration_ms)
            zone['slowest_ms'] = max(zone['slowest_ms'], round(duration_ms, 3))
            zone['successful_bytes'] += count_bytes
            ok_bytes += count_bytes
        except OSError as exc:
            errors += 1
            zone['read_errors'] += 1
            if exc.errno in {errno.ENODEV, errno.EACCES, errno.EPERM, errno.ENXIO,
                             errno.EBADF, errno.EINVAL}:
                stopped = 'aborted_device_or_access_error'
        requested += count_bytes
        if stopped != 'completed' or errors >= max_errors:
            stopped = 'aborted_error_limit' if stopped == 'completed' else stopped
            break
    elapsed = max(0, timer() - started)
    ordered = sorted(latencies)
    def percentile(p: float) -> float | None:
        if not ordered:
            return None
        return round(ordered[int((len(ordered) - 1) * p)], 3)
    if errors and stopped == 'completed':
        stopped = 'completed_with_errors'
    return {
        'status': stopped, 'mode': mode, 'readable_bytes': ok_bytes,
        'requested_bytes': requested, 'read_errors': errors,
        'elapsed_seconds': round(elapsed, 3),
        'throughput_mib_s': round(ok_bytes / (1024 * 1024 * elapsed), 3) if elapsed > 0 else None,
        'read_latency_ms': {'median': percentile(.5), 'p95': percentile(.95),
                            'p99': percentile(.99), 'max': percentile(1)},
        'zones': zone_stats, 'latency_sample_count': len(latencies),
        'notes': 'Read-only; sequential sampling affected by OS caches, transport, and other I/O. '
                 'Percentiles may be sampled on large drives. Performance improvement is not proof of reversed physical wear.',
    }


def compare_benchmarks(before: dict, after: dict) -> dict:
    """Compare aligned measurements without inferring device lifespan."""
    for item in (before, after):
        if item.get('status') != 'completed' or item.get('read_errors'):
            raise ValueError('Both benchmarks must complete without read errors')
        if not item.get('source_fingerprint') or not item.get('device_size_bytes'):
            raise ValueError('Benchmark lacks source identity; cannot compare')
    if any(before.get(k) != after.get(k) for k in
           ('source_fingerprint', 'device_size_bytes', 'mode', 'requested_bytes')):
        raise ValueError('Benchmarks differ in source identity, size, mode or coverage')
    def change(a, b):
        return round((b / a - 1) * 100, 2) if a not in (None, 0) and b is not None else None
    return {
        'status': 'comparison_only',
        'read_throughput_change_percent': change(before.get('throughput_mib_s'),
                                                  after.get('throughput_mib_s')),
        'p95_read_latency_change_percent': change(
            before.get('read_latency_ms', {}).get('p95'),
            after.get('read_latency_ms', {}).get('p95')),
        'notes': 'Observed performance only. Repeated randomized-order runs, temperature, cache '
                 'control, device health and independent verification are required before '
                 'claiming improvement. Cannot establish physical-wear reversal.',
    }
