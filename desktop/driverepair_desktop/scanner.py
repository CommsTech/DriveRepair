"""Bounded-memory, strictly read-only external disk surface scans.

A successful read is NOT proof of correct data, nor a repaired sector.
This module never issues write, TRIM, discard, format, or repair commands.
"""

from __future__ import annotations

import ctypes
import errno
import os
import random
import statistics
import stat
import sys
import time
from typing import Callable, Protocol

from .devices import Device


class Reader(Protocol):
    def read_at(self, offset: int, count: int) -> bytes: ...
    def close(self) -> None: ...


class UnixReader:
    def __init__(self, device: Device) -> None:
        if not device.path.startswith("/dev/"):
            raise ValueError("Refusing a non-device path")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        self.fd = os.open(device.path, flags)
        try:
            st = os.fstat(self.fd)
            if sys.platform.startswith("linux") and not stat.S_ISBLK(st.st_mode):
                raise ValueError("Selected device is not a block device")
            if sys.platform == "darwin" and not stat.S_ISCHR(st.st_mode):
                raise ValueError("Selected device is not a raw character device")
            if st.st_rdev != os.stat(device.path).st_rdev:
                raise ValueError("Device path changed during opening")
        except BaseException:
            os.close(self.fd)
            raise

    def read_at(self, offset: int, count: int) -> bytes:
        return os.pread(self.fd, count, offset)

    def close(self) -> None:
        os.close(self.fd)


class WindowsReader:
    """Use Win32 CreateFileW for physical drives; never request GENERIC_WRITE."""

    def __init__(self, device: Device) -> None:
        if sys.platform != "win32" or not device.path.startswith("\\\\.\\PhysicalDrive"):
            raise ValueError("Not a Windows physical drive")
        from ctypes import wintypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                           wintypes.DWORD, ctypes.c_void_p,
                                           wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                                                 ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetFilePointerEx.restype = wintypes.BOOL
        self.kernel.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                         wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        self.kernel.ReadFile.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        # GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, OPEN_EXISTING.
        self.handle = self.kernel.CreateFileW(device.path, 0x80000000, 0x3,
                                              None, 3, 0, None)
        if self.handle == ctypes.c_void_p(-1).value or self.handle is None:
            error = ctypes.get_last_error()
            if error == 5:  # ERROR_ACCESS_DENIED
                raise PermissionError(
                    "Windows denied read access to the physical drive (WinError 5). "
                    "Try launching DriveRepair as Administrator; security policy or "
                    "another restriction may still prevent access. No scan was performed."
                )
            raise ctypes.WinError(error)

    def read_at(self, offset: int, count: int) -> bytes:
        from ctypes import wintypes
        if not self.kernel.SetFilePointerEx(self.handle, ctypes.c_longlong(offset), None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(count)
        received = wintypes.DWORD(0)
        if not self.kernel.ReadFile(self.handle, buffer, count, ctypes.byref(received), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.raw[:received.value]

    def close(self) -> None:
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class ImageReader:
    """Safe regular-file testing, never raw disk writes."""

    def __init__(self, path: str) -> None:
        # Never let the test-image subcommand bypass external-drive eligibility.
        # Check the provided path string before realpath: on Windows, "/dev/null"
        # may resolve to a non-/dev/ path and must still be rejected.
        candidate = path.replace("\\", "/")
        real = os.path.realpath(path).replace("\\", "/")
        windows_dos_device = path.upper().rstrip(":\\/") in {"NUL", "CON", "PRN", "AUX"}
        if (
            candidate.startswith("/dev/")
            or real.startswith("/dev/")
            or path.startswith("\\\\.\\")
            or path.startswith("\\\\?\\")
            or windows_dos_device
        ):
            raise ValueError("Raw devices cannot be scanned through scan-image")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_BINARY", 0)
        self.fd = os.open(path, flags)
        if not stat.S_ISREG(os.fstat(self.fd).st_mode):
            os.close(self.fd)
            raise ValueError("Image testing requires a regular file")

    def read_at(self, offset: int, count: int) -> bytes:
        if hasattr(os, "pread"):
            return os.pread(self.fd, count, offset)
        os.lseek(self.fd, offset, os.SEEK_SET)
        return os.read(self.fd, count)

    def close(self) -> None:
        os.close(self.fd)


def open_device_readonly(device: Device) -> Reader:
    if sys.platform == "win32":
        return WindowsReader(device)
    return UnixReader(device)


def scan_offsets(size: int, chunk: int, mode: str, samples: int, sample_seed: int | None = None):
    if size <= 0 or chunk <= 0 or samples < 1 or mode not in {"sample", "full", "triage"}:
        raise ValueError("Invalid scan parameters")
    blocks = (size + chunk - 1) // chunk
    if mode == "full":
        for index in range(blocks):
            yield index * chunk, min(chunk, size - index * chunk)
    elif mode == "sample":
        n = min(samples, blocks)
        for i in range(n):
            index = (i * (blocks - 1) // (n - 1)) if n > 1 else 0
            yield index * chunk, min(chunk, size - index * chunk)
    else:
        # Reproducible stratified sampling. Start/end are included; every
        # interior stratum uses a deterministic pseudo-random offset. This
        # samples locations, not a statistically proven health distribution.
        n = min(samples, blocks)
        rng = random.Random(0xD12E5C4A ^ blocks ^ n ^ (sample_seed or 0))
        selected = set()
        for i in range(n):
            lo = i * blocks // n
            hi = min(blocks, (i + 1) * blocks // n)
            index = (0 if i == 0 else blocks - 1 if i == n - 1
                     else rng.randrange(lo, max(lo + 1, hi)))
            selected.add(index)
        for index in sorted(selected):
            yield index * chunk, min(chunk, size - index * chunk)


def scan_reader(reader: Reader, *, size: int, sector: int, mode: str,
                samples: int = 128, chunk: int = 1024 * 1024, max_errors: int = 16,
                compare_suspects: bool = False, adaptive_io: bool = False,
                history_hints: list[dict] | None = None,
                adaptive_min_chunk: int | None = None,
                adaptive_max_chunk: int | None = None,
                sample_seed: int | None = None,
                progress: Callable[..., None] | None = None) -> dict:
    if (not 0 < sector <= 1024 * 1024 or size <= 0 or size % sector or
            chunk < sector or chunk % sector or not 1 <= max_errors <= 10000 or
            not 1 <= samples <= 100000):
        raise ValueError("Invalid size, alignment, sample count or error limit")
    if adaptive_io and mode == 'full':
        from .adaptive_scan import adaptive_full_scan
        return adaptive_full_scan(reader, size=size, sector=sector, chunk=chunk,
                                  max_errors=max_errors, progress=progress,
                                  min_chunk=adaptive_min_chunk, max_chunk=adaptive_max_chunk)
    blocks = (size + chunk - 1) // chunk
    baseline = list(scan_offsets(size, chunk, mode, samples, sample_seed)) if mode != 'full' else None
    if mode == 'triage' and history_hints:
        # Anomaly history is only a HINT. Every bookmarked location is re-read;
        # never reuse historical success as evidence for a current rewrite.
        known = {off for off, _ in baseline}
        for item in history_hints[:64]:
            off = item.get('offset')
            if type(off) is not int or not 0 <= off < size:
                continue
            off = off // chunk * chunk
            if off not in known:
                baseline.append((off, min(chunk, size - off)))
                known.add(off)
        baseline.sort()
    planned = blocks if mode == 'full' else len(baseline)
    checked = readable = failures = 0
    failed_ranges: list[dict] = []
    completed = 0
    started = time.monotonic()
    status = 'completed'
    latencies: list[float] = []
    # Bounded ring for live median during full-surface passes (avoid retaining
    # every 1 MiB sample latency for multi-TB media in RAM).
    latency_window: list[float] = []
    latency_window_cap = 512
    probe_latencies: list[tuple[int, float]] = []
    anomalous_indices: list[int] = []
    examined: set[int] = set()
    slow_regions: list[dict] = []
    slow_region_count = 0

    def _median_ms() -> float | None:
        if not latency_window:
            return None
        return float(statistics.median(latency_window))

    def attempt(offset: int, length: int) -> bool:
        nonlocal checked, readable, failures, completed, status, slow_region_count
        checked += length
        completed += 1
        if mode == 'triage':
            examined.add(offset // chunk)
        error = None
        error_class = None
        disconnect = False
        t0 = time.monotonic()
        try:
            data = reader.read_at(offset, length)
            if len(data) != length:
                error = f'short read ({len(data)} of {length} bytes)'
            else:
                readable += length
        except OSError as exc:
            winerror = getattr(exc, 'winerror', None)
            error = (f'read failed ({type(exc).__name__}, errno={exc.errno}'
                     + (f', winerror={winerror}' if winerror is not None else '') + ')')
            from .adaptive_scan import classify_error
            error_class = classify_error(exc)
            if error_class in {'device_or_access_unavailable', 'invalid_read_request'}:
                status = 'aborted_device_or_access_error'
                disconnect = error_class == 'device_or_access_unavailable'
        latency_ms = (time.monotonic() - t0) * 1000
        if error:
            failures += 1
            anomalous_indices.append(offset // chunk)
            if len(failed_ranges) < 1000:
                failed_ranges.append({'offset': offset, 'length': length, 'error': error,
                                      'interpretation': error_class or 'read_failure_needs_investigation'})
        else:
            # All modes track latency so GUI/CLI can surface slow spots live.
            latency_window.append(latency_ms)
            if len(latency_window) > latency_window_cap:
                del latency_window[: len(latency_window) - latency_window_cap]
            if mode == 'triage':
                latencies.append(latency_ms)
                probe_latencies.append((offset, latency_ms))
            else:
                med = _median_ms() or 0.0
                threshold = max(50.0, med * 4)
                if latency_ms >= threshold:
                    slow_region_count += 1
                    if len(slow_regions) < 1000:
                        slow_regions.append({
                            'offset': offset,
                            'length': length,
                            'latency_ms': round(latency_ms, 3),
                            'median_ms': round(med, 3),
                        })
                    if mode == 'triage':
                        anomalous_indices.append(offset // chunk)
        med = _median_ms()
        info = {
            'offset': offset,
            'length': length,
            'latency_ms': round(latency_ms, 3),
            'median_ms': None if med is None else round(med, 3),
            'failed': error is not None,
            'error_class': error_class,
            'disconnect': disconnect,
            'attempted_bytes': checked,
            'readable_bytes': readable,
            'read_error_chunks': failures,
        }
        if progress:
            try:
                progress(min(completed, planned), planned, info)
            except TypeError:
                progress(min(completed, planned), planned)
        if failures >= max_errors and status == 'completed':
            status = 'aborted_error_limit'
        return error is None

    offsets = baseline if baseline is not None else scan_offsets(size, chunk, mode, samples)
    for offset, length in offsets:
        attempt(offset, length)
        if status.startswith('aborted'):
            break

    # Triage's second stage investigates neighboring chunks of read failures
    # and slow samples, *not* the whole drive. Never re-read an already checked
    # region and never permit unbounded growth of this work list.
    if mode == 'triage' and not status.startswith('aborted'):
        median_ms = statistics.median(latencies) if latencies else 0.0
        threshold = max(50.0, median_ms * 4)
        # Replace any in-pass slow bookmarks with the definitive triage set.
        slow_regions = []
        # We cannot retroactively detect which probes were slow without storing
        # their latency, so capture probe timings in `attempt` below.
        for off, latency in probe_latencies:
            if latency >= threshold:
                anomalous_indices.append(off // chunk)
                slow_regions.append({'offset': off, 'latency_ms': round(latency, 3)})
        suspects = sorted(set(anomalous_indices))
        budget = min(samples, 4096)
        neighbors = set()
        for suspect in suspects:
            for delta in (-2, -1, 1, 2):
                idx = suspect + delta
                if 0 <= idx < blocks and idx not in examined:
                    neighbors.add(idx)
                    if len(neighbors) >= budget:
                        break
            if len(neighbors) >= budget:
                break
        planned += len(neighbors)
        for index in sorted(neighbors):
            offset = index * chunk
            attempt(offset, min(chunk, size - offset))
            if status.startswith('aborted'):
                break

    # Extra targeted reads are optional: discrepancies flag instability, NOT the
    # original/correct value. Only revisit suspicious samples, not all LBAs.
    inconsistent_reads: list[dict] = []
    repeated_read_errors = 0
    repeat_probe_failed_ranges: list[dict] = []
    if compare_suspects and mode == 'triage' and not status.startswith('aborted'):
        candidates = sorted(set(anomalous_indices))[:min(64, samples)]
        for index in candidates:
            off = index * chunk
            length = min(chunk, size - off)
            try:
                first = reader.read_at(off, length)
                second = reader.read_at(off, length)
                if len(first) != length or len(second) != length:
                    repeated_read_errors += 1
                    repeat_probe_failed_ranges.append({'offset': off, 'length': length})
                elif first != second:
                    inconsistent_reads.append({'offset': off, 'length': length,
                                               'interpretation': 'Inconsistent repeated reads; correct bytes UNKNOWN'})
            except OSError:
                repeated_read_errors += 1
                repeat_probe_failed_ranges.append({'offset': off, 'length': length})
        if inconsistent_reads and status == 'completed':
            status = 'completed_with_inconsistent_reads'
    if status == 'completed' and failures:
        status = 'completed_with_read_errors'
    elif status == 'completed' and slow_regions:
        status = 'completed_with_slow_regions'
    return {
        'status': status,
        'mode': mode,
        'device_size_bytes': size,
        'logical_sector_bytes': sector,
        'readable_bytes': readable,
        'attempted_bytes': checked,
        'attempted_chunks': completed,
        'planned_chunks': planned,
        'read_error_chunks': failures,
        'read_error_ranges': failed_ranges,
        'read_error_ranges_truncated': failures > len(failed_ranges),
        'slow_regions': slow_regions,
        'historical_hints_used': len(history_hints or []),
        'sampling_seed': sample_seed if mode == 'triage' else None,
        'slow_region_count': max(slow_region_count, len(slow_regions)),
        'slow_regions_truncated': slow_region_count > 1000,
        'inconsistent_reads': inconsistent_reads,
        'repeat_probe_failures': repeated_read_errors,
        'repeat_probe_failed_ranges': repeat_probe_failed_ranges,
        'extra_suspect_reads': 2 * min(len(set(anomalous_indices)), 64, samples) if compare_suspects and mode == 'triage' else 0,
        'follow_up_chunks': max(0, completed - (len(baseline) if baseline is not None else blocks)),
        'surface_coverage_pct': round(100 * (sum(min(chunk, size - i * chunk) for i in examined)
                                             if mode == 'triage' else min(size, checked)) / size, 6),
        'unique_address_bytes': (sum(min(chunk, size - i * chunk) for i in examined)
                                 if mode == 'triage' else min(size, checked)),
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'notes': ('TRIAGE IS A SPOT-CHECK, not a health certification. ' if mode == 'triage' else '') +
                 'Readability only; no sector repaired, no writes, no correctness guarantee. '
                 'Errors locate affected CHUNKS, not defective individual sectors. ' +
                 ('Optional repeated-suspect checks can detect inconsistency but cannot establish correct bits.'
                  if compare_suspects else ''),
    }
