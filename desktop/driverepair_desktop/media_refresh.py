"""In-Place Media Refresh — rolling-journal transactional rewrite engine.

Dedicated destructive mode alongside image-based recovery. It never replaces
rescue/imaging workflows and does NOT claim wear reversal or recovery of
already-unreadable data.

Rolling journal transaction states for the active region:
  SAVED → WRITING → VERIFIED → COMMITTED

Original bytes remain in the journal until VERIFIED+COMMITTED. Unreadable or
inconsistent regions are skipped — never rewritten with invented data.

Modes:
  adaptive — probe latency, refresh only unusually slow/consistent regions
  full     — sequential whole-surface refresh (high risk; long on large disks)

PUBLIC RELEASE NOT APPROVED. Live hardware use remains unvalidated until
sacrificial interrupt/USB-disconnect tests pass.
"""
from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import stat
import sys
import time
from typing import Callable, Protocol

from .compat import binary_open_flags, pwrite
from .devices import Device
from .recovery import _merge_ranges, _state_save

STATE_SAVED = "SAVED"
STATE_WRITING = "WRITING"
STATE_VERIFIED = "VERIFIED"
STATE_COMMITTED = "COMMITTED"

_FATAL = {errno.ENODEV, errno.EBADF, errno.EPERM, errno.EACCES,
          errno.ENOENT, errno.EINVAL, errno.ENXIO}


class ReadWriter(Protocol):
    def read_at(self, offset: int, count: int) -> bytes: ...
    def write_at(self, offset: int, data: bytes) -> int: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...


class ImageReadWriter:
    """Regular-file media for synthetic validation and fault injection."""

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
    """Win32 physical-drive RW handle with write-through."""

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
        access = 0x80000000 | 0x40000000
        flags = 0x80000000  # FILE_FLAG_WRITE_THROUGH
        self.handle = self.kernel.CreateFileW(device.path, access, 0x3, None, 3, flags, None)
        if self.handle == ctypes.c_void_p(-1).value or self.handle is None:
            raise ctypes.WinError(ctypes.get_last_error())
        self._volume_handles: list[int] = []

    def lock_volumes(self, disk_number: int) -> None:
        """FSCTL_LOCK_VOLUME + FSCTL_DISMOUNT_VOLUME for volumes on this disk."""
        from ctypes import wintypes
        import subprocess

        script = (
            f"Get-Partition -DiskNumber {int(disk_number)} | "
            "Where-Object { $_.DriveLetter } | "
            "ForEach-Object { $_.DriveLetter } | ConvertTo-Json -Compress"
        )
        try:
            raw = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, check=True, timeout=25,
            ).stdout.decode("utf-8-sig").strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            raise RuntimeError(f"Unable to enumerate volumes for exclusive lock: {exc}") from exc
        letters: list[str] = []
        if raw:
            parsed = json.loads(raw)
            if isinstance(parsed, str):
                letters = [parsed]
            elif isinstance(parsed, list):
                letters = [str(x) for x in parsed]
        FSCTL_LOCK_VOLUME = 0x00090018
        FSCTL_DISMOUNT_VOLUME = 0x00090020
        self.kernel.DeviceIoControl.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
        ]
        self.kernel.DeviceIoControl.restype = wintypes.BOOL
        for letter in letters:
            path = rf"\\.\{letter}:"
            handle = self.kernel.CreateFileW(path, 0x80000000 | 0x40000000, 0x3, None, 3, 0, None)
            if handle == ctypes.c_void_p(-1).value or handle is None:
                raise RuntimeError(
                    f"Volume {letter}: is present on the patient but could not be opened exclusively. "
                    "Unmount/stop using the filesystem before in-place refresh."
                )
            returned = wintypes.DWORD(0)
            if not self.kernel.DeviceIoControl(handle, FSCTL_LOCK_VOLUME, None, 0, None, 0,
                                               ctypes.byref(returned), None):
                self.kernel.CloseHandle(handle)
                raise RuntimeError(
                    f"FSCTL_LOCK_VOLUME failed for {letter}: — filesystem appears in use"
                )
            self.kernel.DeviceIoControl(handle, FSCTL_DISMOUNT_VOLUME, None, 0, None, 0,
                                        ctypes.byref(returned), None)
            self._volume_handles.append(handle)

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
        for handle in self._volume_handles:
            self.kernel.CloseHandle(handle)
        self._volume_handles.clear()
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class UnixReadWriter:
    def __init__(self, device: Device) -> None:
        if not device.path.startswith("/dev/"):
            raise ValueError("Refusing a non-device path")
        flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_SYNC", 0)
        flags = binary_open_flags(flags)
        if sys.platform.startswith("linux"):
            flags |= getattr(os, "O_EXCL", 0)
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
        media = WindowsReadWriter(device)
        number = int(device.path.rsplit("PhysicalDrive", 1)[-1])
        media.lock_volumes(number)
        return media
    return UnixReadWriter(device)


def require_destructive_acknowledgements(
    *,
    ack_risk: bool,
    ack_destructive: bool,
    ack_no_backup: bool,
    ack_data_loss_risk: bool,
    ack_usb_bridge_risk: bool,
    bus: str,
    ack_unvalidated_hardware: bool = True,
    require_unvalidated: bool = False,
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
    if require_unvalidated and not ack_unvalidated_hardware:
        missing.append("--ack-unvalidated-hardware")
    if missing:
        raise ValueError(
            "In-place refresh requires explicit acknowledgements: " + ", ".join(missing)
            + ". Rolling journal protects only the active region, not the whole disk."
        )


def assert_stable_identity(expected: Device, observed: Device) -> None:
    if expected.fingerprint != observed.fingerprint:
        raise RuntimeError("Patient identity changed (model/size/serial/bus/path)")
    if expected.size_bytes != observed.size_bytes or expected.sector_size != observed.sector_size:
        raise RuntimeError("Patient capacity or sector size changed")


def assert_patient_idle_windows(device: Device) -> None:
    """Refuse refresh when Windows reports a drive letter on the patient."""
    if sys.platform != "win32":
        return
    import subprocess
    number = int(device.path.rsplit("PhysicalDrive", 1)[-1])
    script = (
        f"$p = Get-Partition -DiskNumber {number} -ErrorAction Stop; "
        "$letters = @($p | Where-Object { $_.DriveLetter } | ForEach-Object { [string]$_.DriveLetter }); "
        "$letters | ConvertTo-Json -Compress"
    )
    try:
        raw = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, check=True, timeout=25,
        ).stdout.decode("utf-8-sig").strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Unable to verify patient mount state: {exc}") from exc
    if not raw or raw == "null":
        return
    parsed = json.loads(raw)
    letters = [parsed] if isinstance(parsed, str) else list(parsed or [])
    if letters:
        raise RuntimeError(
            "Patient has mounted drive letter(s) "
            + ",".join(letters)
            + "; unmount/stop using the filesystem before in-place refresh"
        )


def _journal_paths(journal_dir: str) -> tuple[str, str]:
    root = os.path.abspath(journal_dir)
    return root, os.path.join(root, "meta.json")


def _atomic_write_bytes(path: str, data: bytes) -> None:
    temp = path + ".pending"
    if os.path.lexists(temp):
        os.unlink(temp)
    fd = os.open(temp, binary_open_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL), 0o600)
    try:
        offset = 0
        while offset < len(data):
            n = os.write(fd, data[offset:])
            if n <= 0:
                raise OSError(errno.EIO, "journal blob write stalled")
            offset += n
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temp, path)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _classify_os_error(exc: OSError) -> str:
    if exc.errno in {errno.ENODEV, errno.ENXIO}:
        return "transport_or_disconnect"
    if exc.errno in {errno.EIO, errno.EILSEQ}:
        return "media_or_io"
    if exc.errno in {errno.ETIMEDOUT}:
        return "timeout"
    return "os_error"


def _read_consistent(media: ReadWriter, offset: int, length: int, reads: int) -> bytes:
    if reads < 2:
        raise ValueError("consistency_reads must be >= 2")
    first = media.read_at(offset, length)
    if len(first) != length:
        raise OSError(errno.EIO, f"short read ({len(first)} of {length})")
    for _ in range(reads - 1):
        again = media.read_at(offset, length)
        if again != first:
            raise RuntimeError("inconsistent_reads")
    return first


def _write_all_at(media: ReadWriter, offset: int, data: bytes) -> None:
    wrote = 0
    while wrote < len(data):
        n = media.write_at(offset + wrote, data[wrote:])
        if n <= 0:
            raise OSError(errno.EIO, "Refresh write made no progress")
        wrote += n
    media.flush()


def _probe_adaptive_targets(
    media: ReadWriter,
    *,
    size: int,
    chunk: int,
    samples: int,
    slow_multiplier: float,
) -> list[tuple[int, int]]:
    """Return slow-but-readable regions for Adaptive Refresh."""
    blocks = max(1, (size + chunk - 1) // chunk)
    n = min(samples, blocks)
    timings: list[tuple[int, int, float]] = []
    for i in range(n):
        index = (i * (blocks - 1) // (n - 1)) if n > 1 else 0
        offset = index * chunk
        length = min(chunk, size - offset)
        if length <= 0:
            continue
        started = time.perf_counter()
        try:
            data = media.read_at(offset, length)
            if len(data) != length:
                continue
        except OSError:
            continue
        elapsed = time.perf_counter() - started
        timings.append((offset, length, elapsed))
    if not timings:
        return []
    times = sorted(t for _, _, t in timings)
    median = times[len(times) // 2]
    threshold = max(median * slow_multiplier, median + 1e-6)
    return [(o, l) for o, l, t in timings if t >= threshold]


def _default_meta(
    *,
    source_token: str,
    size: int,
    sector: int,
    chunk: int,
    mode: str,
    verify: bool,
    consistency_reads: int,
) -> dict:
    return {
        "schema": 2,
        "operation": "media_refresh_rolling",
        "mode": mode,
        "size": size,
        "sector": sector,
        "chunk": chunk,
        "source_token": source_token,
        "verify": verify,
        "consistency_reads": consistency_reads,
        "cursor": 0,
        "queue": [],
        "rewritten_bytes": 0,
        "verified_bytes": 0,
        "skipped_ranges": [],
        "inconsistent_ranges": [],
        "failed_read_attempts": 0,
        "failed_write_attempts": 0,
        "transaction": None,
        "status": "in_progress",
        "notes": (
            "Rolling journal protects only the active region (SAVED→WRITING→VERIFIED→COMMITTED). "
            "Not a substitute for a full backup. Unreadable/inconsistent sectors are never rewritten."
        ),
    }


def _recover_interrupted_transaction(media: ReadWriter, journal_dir: str, meta: dict) -> dict:
    """Resume policy for a partial transaction; never invents bytes."""
    tx = meta.get("transaction")
    if not tx:
        return meta
    state = tx.get("state")
    offset = int(tx["offset"])
    length = int(tx["length"])
    blob = os.path.join(journal_dir, "region.bin")
    digest = tx.get("sha256")
    if state == STATE_COMMITTED:
        meta["transaction"] = None
        if os.path.isfile(blob):
            os.unlink(blob)
        return meta
    if state == STATE_VERIFIED:
        # Commit: drop blob and advance accounting if needed.
        meta["transaction"] = None
        if os.path.isfile(blob):
            os.unlink(blob)
        return meta
    if state in {STATE_SAVED, STATE_WRITING}:
        if not os.path.isfile(blob):
            raise RuntimeError(
                f"Interrupted transaction in {state} but region.bin missing; "
                "manual review required before continuing"
            )
        with open(blob, "rb") as handle:
            data = handle.read()
        if len(data) != length or _sha256(data) != digest:
            raise RuntimeError("Journal region blob failed integrity check; refusing resume")
        # Always restore preserved bytes before continuing after WRITING/SAVED.
        _write_all_at(media, offset, data)
        tx["state"] = STATE_SAVED
        meta["transaction"] = tx
        _state_save(os.path.join(journal_dir, "meta.json"), meta)
        return meta
    raise RuntimeError(f"Unknown transaction state {state!r}")


def refresh_media(
    media: ReadWriter,
    *,
    size: int,
    sector: int,
    source_token: str,
    journal: str,
    chunk: int = 1024 * 1024,
    mode: str = "adaptive",
    verify: bool = True,
    resume: bool = False,
    max_errors: int = 4096,
    consistency_reads: int = 2,
    adaptive_samples: int = 256,
    slow_multiplier: float = 2.0,
    progress: Callable[[dict], None] | None = None,
    identity_check: Callable[[], None] | None = None,
) -> dict:
    if mode not in {"adaptive", "full"}:
        raise ValueError("mode must be adaptive or full")
    if size <= 0 or sector <= 0 or size % sector or chunk < sector or chunk % sector:
        raise ValueError("Invalid size/sector/chunk alignment for refresh")
    if not 1 <= max_errors <= 100000 or consistency_reads < 2:
        raise ValueError("Invalid max_errors or consistency_reads")

    journal_dir, meta_path = _journal_paths(journal)
    blob_path = os.path.join(journal_dir, "region.bin")

    if resume:
        if not os.path.isdir(journal_dir) or not os.path.isfile(meta_path):
            raise FileNotFoundError("Cannot resume; rolling journal missing")
        with open(meta_path, encoding="utf-8") as handle:
            meta = json.loads(handle.read())
        if meta.get("schema") != 2 or meta.get("operation") != "media_refresh_rolling":
            raise ValueError("Journal is not a rolling media_refresh state directory")
        if meta.get("source_token") != source_token or meta.get("size") != size:
            raise RuntimeError("Journal does not match this media identity/size")
        if meta.get("sector") != sector or meta.get("chunk") != chunk or meta.get("mode") != mode:
            raise RuntimeError("Journal sector/chunk/mode does not match this run")
        meta = _recover_interrupted_transaction(media, journal_dir, meta)
    else:
        if os.path.lexists(journal_dir):
            raise FileExistsError("Refresh journal already exists; use --resume")
        os.makedirs(journal_dir, mode=0o700)
        meta = _default_meta(
            source_token=source_token, size=size, sector=sector, chunk=chunk,
            mode=mode, verify=verify, consistency_reads=consistency_reads,
        )
        if mode == "adaptive":
            targets = _probe_adaptive_targets(
                media, size=size, chunk=chunk, samples=adaptive_samples,
                slow_multiplier=slow_multiplier,
            )
            meta["queue"] = [[o, l] for o, l in targets]
            meta["adaptive_targets"] = len(targets)
        else:
            meta["queue"] = None  # sequential via cursor
        _state_save(meta_path, meta)

    started = time.monotonic()
    status = "completed"

    def save() -> None:
        _state_save(meta_path, meta)
        if progress:
            progress(dict(meta))

    def next_region() -> tuple[int, int] | None:
        if mode == "adaptive":
            queue = meta.get("queue") or []
            if not queue:
                return None
            offset, length = queue.pop(0)
            meta["queue"] = queue
            return int(offset), int(length)
        cursor = int(meta["cursor"])
        if cursor >= size:
            return None
        length = min(chunk, size - cursor)
        if length % sector:
            length -= length % sector
        if length <= 0:
            return None
        return cursor, length

    try:
        # Finish a restored SAVED transaction before selecting new regions.
        while True:
            if identity_check:
                identity_check()
            tx = meta.get("transaction")
            if tx and tx.get("state") == STATE_SAVED:
                offset = int(tx["offset"])
                length = int(tx["length"])
                with open(blob_path, "rb") as handle:
                    data = handle.read()
                if len(data) != length or _sha256(data) != tx["sha256"]:
                    raise RuntimeError("SAVED region blob corrupted")
                tx["state"] = STATE_WRITING
                meta["transaction"] = tx
                save()
                try:
                    _write_all_at(media, offset, data)
                except OSError as exc:
                    meta["failed_write_attempts"] = int(meta["failed_write_attempts"]) + 1
                    meta["last_error_class"] = _classify_os_error(exc)
                    # Best-effort restore of journaled original bytes after a failed write.
                    try:
                        _write_all_at(media, offset, data)
                    except OSError:
                        pass
                    meta["skipped_ranges"] = _merge_ranges(
                        list(meta.get("skipped_ranges") or []) + [[offset, length]]
                    )
                    meta["transaction"] = None
                    if os.path.isfile(blob_path):
                        os.unlink(blob_path)
                    if exc.errno in _FATAL:
                        status = "aborted_device_or_access_error"
                        break
                    save()
                    if int(meta["failed_read_attempts"]) + int(meta["failed_write_attempts"]) >= max_errors:
                        status = "aborted_error_limit"
                        break
                    continue
                if verify:
                    try:
                        check = media.read_at(offset, length)
                        if check != data:
                            meta["skipped_ranges"] = _merge_ranges(
                                list(meta.get("skipped_ranges") or []) + [[offset, length]]
                            )
                            # Restore journaled original again — already on disk ideally.
                            _write_all_at(media, offset, data)
                            meta["transaction"] = None
                            if os.path.isfile(blob_path):
                                os.unlink(blob_path)
                            save()
                            continue
                        meta["verified_bytes"] = int(meta["verified_bytes"]) + length
                    except OSError as exc:
                        meta["last_error_class"] = _classify_os_error(exc)
                        _write_all_at(media, offset, data)
                        meta["transaction"] = None
                        if os.path.isfile(blob_path):
                            os.unlink(blob_path)
                        save()
                        continue
                tx["state"] = STATE_VERIFIED
                meta["transaction"] = tx
                save()
                meta["rewritten_bytes"] = int(meta["rewritten_bytes"]) + length
                if mode == "full":
                    meta["cursor"] = offset + length
                tx["state"] = STATE_COMMITTED
                meta["transaction"] = None
                if os.path.isfile(blob_path):
                    os.unlink(blob_path)
                save()
                continue

            region = next_region()
            if region is None:
                break
            offset, length = region
            try:
                data = _read_consistent(media, offset, length, consistency_reads)
            except RuntimeError as exc:
                if str(exc) == "inconsistent_reads":
                    meta["inconsistent_ranges"] = _merge_ranges(
                        list(meta.get("inconsistent_ranges") or []) + [[offset, length]]
                    )
                    if mode == "full":
                        meta["cursor"] = offset + length
                    save()
                    continue
                raise
            except OSError as exc:
                meta["failed_read_attempts"] = int(meta["failed_read_attempts"]) + 1
                meta["skipped_ranges"] = _merge_ranges(
                    list(meta.get("skipped_ranges") or []) + [[offset, length]]
                )
                meta["last_error_class"] = _classify_os_error(exc)
                if mode == "full":
                    meta["cursor"] = offset + length
                if exc.errno in _FATAL:
                    status = "aborted_device_or_access_error"
                    save()
                    break
                save()
                if int(meta["failed_read_attempts"]) + int(meta["failed_write_attempts"]) >= max_errors:
                    status = "aborted_error_limit"
                    break
                continue

            # SAVED: durable preserve before any patient write.
            _atomic_write_bytes(blob_path, data)
            meta["transaction"] = {
                "state": STATE_SAVED,
                "offset": offset,
                "length": length,
                "sha256": _sha256(data),
            }
            save()
            # Loop continues into SAVED handler above.
    finally:
        pass

    if status == "completed":
        if meta.get("skipped_ranges") or meta.get("inconsistent_ranges"):
            status = "completed_with_skips_or_verify_failures"
        if meta.get("transaction"):
            status = "interrupted"
        elif mode == "full" and int(meta["cursor"]) < size:
            status = "interrupted"
        elif mode == "adaptive" and (meta.get("queue") or []):
            status = "interrupted"

    meta["status"] = status
    meta["elapsed_seconds"] = round(time.monotonic() - started, 3)
    save()
    return {
        "schema": 2,
        "operation": "media_refresh_rolling",
        "status": meta["status"],
        "mode": mode,
        "size": size,
        "sector": sector,
        "chunk": chunk,
        "source_token": source_token,
        "journal": journal_dir,
        "cursor": meta.get("cursor"),
        "queue_remaining": len(meta.get("queue") or []),
        "rewritten_bytes": meta["rewritten_bytes"],
        "verified_bytes": meta["verified_bytes"],
        "skipped_ranges": meta.get("skipped_ranges") or [],
        "inconsistent_ranges": meta.get("inconsistent_ranges") or [],
        "failed_read_attempts": meta["failed_read_attempts"],
        "failed_write_attempts": meta["failed_write_attempts"],
        "transaction": meta.get("transaction"),
        "last_error_class": meta.get("last_error_class"),
        "verify": verify,
        "consistency_reads": consistency_reads,
        "elapsed_seconds": meta["elapsed_seconds"],
        "notes": meta["notes"],
    }
