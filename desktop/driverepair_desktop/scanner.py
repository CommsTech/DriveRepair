"""Bounded-memory, strictly read-only external disk surface scans.

A successful read is NOT proof of correct data, nor a repaired sector.
This module never issues write, TRIM, discard, format, or repair commands.
"""

from __future__ import annotations

import ctypes
import errno
import os
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
            raise ctypes.WinError(ctypes.get_last_error())

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
        self.fd = os.open(path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
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


def scan_offsets(size: int, chunk: int, mode: str, samples: int):
    if size <= 0 or chunk <= 0 or samples < 1 or mode not in {"sample", "full"}:
        raise ValueError("Invalid scan parameters")
    blocks = (size + chunk - 1) // chunk
    if mode == "full":
        for index in range(blocks):
            yield index * chunk, min(chunk, size - index * chunk)
    else:
        n = min(samples, blocks)
        for i in range(n):
            index = (i * (blocks - 1) // (n - 1)) if n > 1 else 0
            yield index * chunk, min(chunk, size - index * chunk)


def scan_reader(reader: Reader, *, size: int, sector: int, mode: str,
                samples: int = 128, chunk: int = 1024 * 1024, max_errors: int = 16,
                progress: Callable[[int, int], None] | None = None) -> dict:
    if (not 0 < sector <= 1024 * 1024 or size <= 0 or size % sector or
            chunk < sector or chunk % sector or not 1 <= max_errors <= 10000 or
            not 1 <= samples <= 100000):
        raise ValueError("Invalid size, alignment, sample count or error limit")
    blocks = (size + chunk - 1) // chunk
    planned = blocks if mode == "full" else min(samples, blocks)
    checked = readable = failures = 0
    failed_ranges: list[dict] = []
    completed = 0
    started = time.monotonic()
    status = "completed"
    for offset, length in scan_offsets(size, chunk, mode, samples):
        checked += length
        completed += 1
        error = None
        try:
            data = reader.read_at(offset, length)
            if len(data) != length:
                error = f"short read ({len(data)} of {length} bytes)"
            else:
                readable += length
        except OSError as exc:
            error = f"read failed ({type(exc).__name__}, errno={exc.errno})"
            if exc.errno in {errno.ENODEV, errno.EBADF, errno.EACCES,
                             errno.EPERM, errno.EINVAL, errno.ENOENT}:
                status = "aborted_device_or_access_error"
        if error:
            failures += 1
            if len(failed_ranges) < 1000:
                failed_ranges.append({"offset": offset, "length": length, "error": error})
        if progress:
            progress(completed, planned)
        if status.startswith("aborted"):
            break
        if failures >= max_errors:
            status = "aborted_error_limit"
            break
    if status == "completed" and failures:
        status = "completed_with_read_errors"
    return {
        "status": status,
        "mode": mode,
        "device_size_bytes": size,
        "logical_sector_bytes": sector,
        "readable_bytes": readable,
        "attempted_bytes": checked,
        "attempted_chunks": completed,
        "planned_chunks": planned,
        "read_error_chunks": failures,
        "read_error_ranges": failed_ranges,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "notes": ("Readability only; no sector repaired, no source writes, "
                  "no checksum-based correctness guarantee. Failed ranges are "
                  "chunk-sized and not confirmed individual defective sectors."),
    }
