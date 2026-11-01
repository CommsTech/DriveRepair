"""Experimental in-place media refresh (read → rewrite same bytes → optional verify).

DESTRUCTIVE. This module can open a patient device for writing. It never invents
data for unread sectors: a failed read skips that range and leaves media unchanged.

This does NOT reverse physical wear, repair scratched platters, or restore NAND
endurance. A successful rewrite may only refresh a weak recording or trigger
firmware remapping. PUBLIC RELEASE NOT APPROVED.
"""
from __future__ import annotations

import ctypes
import errno
import json
import os
import stat
import sys
import time
from typing import Callable, Protocol

from .compat import binary_open_flags, pwrite
from .devices import Device
from .recovery import _merge_ranges, _state_save


class ReadWriter(Protocol):
    def read_at(self, offset: int, count: int) -> bytes: ...
    def write_at(self, offset: int, data: bytes) -> int: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...


_FATAL = {errno.ENODEV, errno.EBADF, errno.EPERM, errno.EACCES,
          errno.ENOENT, errno.EINVAL, errno.ENXIO}


class ImageReadWriter:
    """Regular-file read/write helper for synthetic tests and image experiments."""

    def __init__(self, path: str) -> None:
        candidate = path.replace("\\", "/")
        real = os.path.realpath(path).replace("\\", "/")
        if (
            candidate.startswith("/dev/")
            or real.startswith("/dev/")
            or path.startswith("\\\\.\\")
            or path.startswith("\\\\?\\")
        ):
            raise ValueError("Raw devices cannot be refreshed through refresh-image")
        flags = binary_open_flags(os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        self.fd = os.open(path, flags)
        try:
            if not stat.S_ISREG(os.fstat(self.fd).st_mode):
                raise ValueError("refresh-image requires a regular file")
        except BaseException:
            os.close(self.fd)
            raise

    def read_at(self, offset: int, count: int) -> bytes:
        if hasattr(os, "pread"):
            return os.pread(self.fd, count, offset)
        os.lseek(self.fd, offset, os.SEEK_SET)
        return os.read(self.fd, count)

    def write_at(self, offset: int, data: bytes) -> int:
        return pwrite(self.fd, data, offset)

    def flush(self) -> None:
        os.fsync(self.fd)

    def close(self) -> None:
        os.close(self.fd)


class WindowsReadWriter:
    """Win32 physical-drive handle with GENERIC_READ|GENERIC_WRITE + write-through."""

    def __init__(self, device: Device) -> None:
        if sys.platform != "win32" or not device.path.startswith("\\\\.\\PhysicalDrive"):
            raise ValueError("Not a Windows physical drive")
        from ctypes import wintypes

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.SetFilePointerEx.argtypes = [
            wintypes.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD,
        ]
        self.kernel.SetFilePointerEx.restype = wintypes.BOOL
        self.kernel.ReadFile.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
        ]
        self.kernel.ReadFile.restype = wintypes.BOOL
        self.kernel.WriteFile.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
        ]
        self.kernel.WriteFile.restype = wintypes.BOOL
        self.kernel.FlushFileBuffers.argtypes = [wintypes.HANDLE]
        self.kernel.FlushFileBuffers.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        # GENERIC_READ|GENERIC_WRITE, share R/W, OPEN_EXISTING, WRITE_THROUGH.
        access = 0x80000000 | 0x40000000
        flags = 0x80000000  # FILE_FLAG_WRITE_THROUGH
        self.handle = self.kernel.CreateFileW(device.path, access, 0x3, None, 3, flags, None)
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
        return buffer.raw[: received.value]

    def write_at(self, offset: int, data: bytes) -> int:
        from ctypes import wintypes

        if not self.kernel.SetFilePointerEx(self.handle, ctypes.c_longlong(offset), None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        written = wintypes.DWORD(0)
        buf = ctypes.create_string_buffer(data)
        if not self.kernel.WriteFile(self.handle, buf, len(data), ctypes.byref(written), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(written.value)

    def flush(self) -> None:
        if not self.kernel.FlushFileBuffers(self.handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class UnixReadWriter:
    def __init__(self, device: Device) -> None:
        if not device.path.startswith("/dev/"):
            raise ValueError("Refusing a non-device path")
        flags = binary_open_flags(
            os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_SYNC", 0)
        )
        self.fd = os.open(device.path, flags)
        try:
            st = os.fstat(self.fd)
            if sys.platform.startswith("linux") and not stat.S_ISBLK(st.st_mode):
                raise ValueError("Selected device is not a block device")
            if sys.platform == "darwin" and not stat.S_ISCHR(st.st_mode):
                raise ValueError("Selected device is not a raw character device")
        except BaseException:
            os.close(self.fd)
            raise

    def read_at(self, offset: int, count: int) -> bytes:
        return os.pread(self.fd, count, offset)

    def write_at(self, offset: int, data: bytes) -> int:
        return os.pwrite(self.fd, data, offset)

    def flush(self) -> None:
        os.fsync(self.fd)

    def close(self) -> None:
        os.close(self.fd)


def open_device_readwrite(device: Device) -> ReadWriter:
    if sys.platform == "win32":
        return WindowsReadWriter(device)
    return UnixReadWriter(device)


def require_destructive_acknowledgements(
    *,
    ack_risk: bool,
    ack_destructive: bool,
    ack_no_backup: bool,
    ack_data_loss_risk: bool,
    ack_usb_bridge_risk: bool,
    bus: str,
) -> None:
    missing = []
    if not ack_risk:
        missing.append("--ack-risk")
    if not ack_destructive:
        missing.append("--ack-destructive")
    if not ack_no_backup:
        missing.append("--ack-no-backup")
    if not ack_data_loss_risk:
        missing.append("--ack-data-loss-risk")
    bus_l = (bus or "").lower()
    if bus_l in {"usb", "7", "1394", "4", "sd", "12", "mmc", "13", "firewire", "thunderbolt"}:
        if not ack_usb_bridge_risk:
            missing.append("--ack-usb-bridge-risk")
    if missing:
        raise ValueError(
            "In-place refresh requires explicit acknowledgements: " + ", ".join(missing)
            + ". This writes to the patient media. Unreadable sectors are skipped, not invented."
        )


def refresh_media(
    media: ReadWriter,
    *,
    size: int,
    sector: int,
    source_token: str,
    journal: str,
    chunk: int = 1024 * 1024,
    verify: bool = True,
    resume: bool = False,
    max_errors: int = 4096,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    """Rewrite only fully readable chunks back onto the same media."""
    if size <= 0 or sector <= 0 or size % sector or chunk < sector or chunk % sector:
        raise ValueError("Invalid size/sector/chunk alignment for refresh")
    if not 1 <= max_errors <= 100000:
        raise ValueError("Invalid max_errors")
    journal = os.path.abspath(journal)
    if os.path.dirname(journal) == "":
        raise ValueError("Journal path must include a directory")

    started = time.monotonic()
    if resume:
        if not os.path.isfile(journal):
            raise FileNotFoundError("Cannot resume; journal missing")
        state = json.loads(open(journal, encoding="utf-8").read())
        if state.get("schema") != 1 or state.get("operation") != "media_refresh":
            raise ValueError("Journal is not a media_refresh state file")
        if state.get("source_token") != source_token or state.get("size") != size:
            raise RuntimeError("Journal does not match this media identity/size")
        if state.get("sector") != sector or state.get("chunk") != chunk:
            raise RuntimeError("Journal sector/chunk does not match this run")
        cursor = int(state["cursor"])
        rewritten = int(state["rewritten_bytes"])
        verified_bytes = int(state.get("verified_bytes", 0))
        skipped = list(state.get("skipped_ranges") or [])
        verify_failures = list(state.get("verify_failure_ranges") or [])
        failed_reads = int(state.get("failed_read_attempts", 0))
        failed_writes = int(state.get("failed_write_attempts", 0))
    else:
        if os.path.lexists(journal):
            raise FileExistsError("Refresh journal already exists; use --resume")
        cursor = 0
        rewritten = 0
        verified_bytes = 0
        skipped = []
        verify_failures = []
        failed_reads = 0
        failed_writes = 0

    status = "completed"
    try:
        while cursor < size:
            length = min(chunk, size - cursor)
            if length % sector:
                length -= length % sector
            if length <= 0:
                break
            try:
                data = media.read_at(cursor, length)
            except OSError as exc:
                failed_reads += 1
                skipped.append([cursor, length])
                if exc.errno in _FATAL:
                    status = "aborted_device_or_access_error"
                    break
                cursor += length
                if failed_reads + failed_writes >= max_errors:
                    status = "aborted_error_limit"
                    break
                continue

            if len(data) != length:
                failed_reads += 1
                skipped.append([cursor, length])
                cursor += length
                if failed_reads + failed_writes >= max_errors:
                    status = "aborted_error_limit"
                    break
                continue

            try:
                wrote = 0
                while wrote < len(data):
                    n = media.write_at(cursor + wrote, data[wrote:])
                    if n <= 0:
                        raise OSError(errno.EIO, "Refresh write made no progress")
                    wrote += n
                media.flush()
            except OSError as exc:
                failed_writes += 1
                skipped.append([cursor, length])
                if exc.errno in _FATAL:
                    status = "aborted_device_or_access_error"
                    break
                cursor += length
                if failed_reads + failed_writes >= max_errors:
                    status = "aborted_error_limit"
                    break
                continue

            rewritten += length
            if verify:
                try:
                    check = media.read_at(cursor, length)
                    if check != data:
                        verify_failures.append([cursor, length])
                    else:
                        verified_bytes += length
                except OSError:
                    verify_failures.append([cursor, length])

            cursor += length
            state = {
                "schema": 1,
                "operation": "media_refresh",
                "size": size,
                "sector": sector,
                "chunk": chunk,
                "source_token": source_token,
                "journal": journal,
                "cursor": cursor,
                "rewritten_bytes": rewritten,
                "verified_bytes": verified_bytes,
                "skipped_ranges": _merge_ranges(skipped),
                "verify_failure_ranges": _merge_ranges(verify_failures),
                "failed_read_attempts": failed_reads,
                "failed_write_attempts": failed_writes,
                "verify": verify,
                "status": "in_progress",
            }
            _state_save(journal, state)
            if progress:
                progress(state)
    finally:
        pass

    skipped = _merge_ranges(skipped)
    verify_failures = _merge_ranges(verify_failures)
    if status == "completed":
        if skipped or verify_failures:
            status = "completed_with_skips_or_verify_failures"
        if cursor < size:
            status = "interrupted"
    result = {
        "schema": 1,
        "operation": "media_refresh",
        "status": status,
        "size": size,
        "sector": sector,
        "chunk": chunk,
        "source_token": source_token,
        "journal": journal,
        "cursor": cursor,
        "rewritten_bytes": rewritten,
        "verified_bytes": verified_bytes,
        "skipped_ranges": skipped,
        "verify_failure_ranges": verify_failures,
        "failed_read_attempts": failed_reads,
        "failed_write_attempts": failed_writes,
        "verify": verify,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "notes": (
            "In-place refresh rewrote only fully readable chunks. Skipped ranges were "
            "NOT overwritten with zeros or guessed data. This does not prove wear "
            "reversal, bit-correctness without independent copies, or long-term health."
        ),
    }
    _state_save(journal, {**result, "status": result["status"]})
    return result
