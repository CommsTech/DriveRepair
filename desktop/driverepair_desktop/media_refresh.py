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
from . import release_policy

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
        release_policy.assert_image_patient_writer_available()
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


# GPT Microsoft Reserved (MSR) never exposes a filesystem volume handle.
# Requiring a lock for MSR would refuse every normal GPT external disk.
_WINDOWS_MSR_GPT_TYPE = '{e3c9e316-0b5c-4db8-817d-f92df00215ae}'


def _windows_partition_skips_volume_lock(partition: dict) -> bool:
    gpt = str(partition.get('GptType') or '').strip().casefold()
    msr = _WINDOWS_MSR_GPT_TYPE.casefold()
    return gpt in (msr, msr[1:-1])


def _windows_partition_inventory(disk_number: int) -> list:
    """Enumerate partitions/access paths for a physical disk (fail-closed)."""
    import subprocess

    script = (
        f"$errs = @(); $parts = @(Get-Partition -DiskNumber {int(disk_number)} "
        "-ErrorAction SilentlyContinue -ErrorVariable +errs); "
        "if ($errs.Count -gt 0) { throw 'Unable to establish complete patient partition inventory' }; "
        "@($parts | ForEach-Object { [pscustomobject]@{ PartitionNumber=$_.PartitionNumber; "
        "Type=[string]$_.Type; GptType=[string]$_.GptType; Paths=@($_.AccessPaths) } }) | "
        "ConvertTo-Json -Compress -Depth 4"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, timeout=25,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        raise RuntimeError(f"Cannot enumerate all patient volume access paths: {exc}") from exc
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or b"").decode("utf-8-sig", errors="replace").strip()
        raise RuntimeError(
            f"Cannot enumerate all patient volume access paths: {err or completed.returncode}"
        )
    raw = completed.stdout.decode("utf-8-sig").strip()
    parsed = json.loads(raw) if raw and raw != "null" else []
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        raise RuntimeError('Unexpected Windows partition inventory')
    return parsed


def _windows_partition_lock_signature(partitions) -> tuple:
    """Stable compare key for partition set + lockable paths (TOCTOU recheck)."""
    if isinstance(partitions, dict):
        partitions = [partitions]
    rows = []
    for partition in partitions or []:
        if not isinstance(partition, dict):
            raise RuntimeError('Unexpected Windows partition inventory')
        paths = partition.get('Paths')
        if not isinstance(paths, list):
            raise RuntimeError('Cannot verify patient partition access paths; no physical writes permitted')
        norm_paths = tuple(sorted(str(p) for p in paths if p not in (None, '')))
        rows.append((
            int(partition.get('PartitionNumber') or -1),
            str(partition.get('Type') or ''),
            str(partition.get('GptType') or '').casefold(),
            norm_paths,
        ))
    return tuple(sorted(rows))


def _windows_lock_paths(partitions, *, allow_mounted: bool) -> list[str]:
    """Choose one volume handle per partition; never force unknown mounts.

    Accept a currently assigned letter ONLY when the operator authorized
    temporary exclusive lock+dismount and Windows confirms it is not in use.
    This helper does not itself open, lock or dismount a volume.

    GPT Microsoft Reserved partitions are skipped: they are not mountable and
    never provide AccessPaths. RAW/Unknown/Recovery without a handle still fail closed.
    """
    if isinstance(partitions, dict):
        partitions = [partitions]
    if not isinstance(partitions, list):
        raise RuntimeError('Unexpected Windows partition inventory')
    volume_paths = []
    for partition in partitions:
        if not isinstance(partition, dict) or not isinstance(partition.get('Paths'), list):
            raise RuntimeError('Cannot verify patient partition access paths; no physical writes permitted')
        if _windows_partition_skips_volume_lock(partition):
            # MSR must not carry mount paths; if Windows reports one, fail closed.
            if any(p not in (None, '') for p in partition['Paths']):
                number = partition.get('PartitionNumber', '?')
                raise RuntimeError(
                    f'Partition {number} (Reserved/MSR) unexpectedly exposes AccessPaths; '
                    'refusing raw writes'
                )
            continue
        guids, letters = [], []
        for path in partition['Paths']:
            if path is None or path == '':
                continue
            if not isinstance(path, str):
                raise RuntimeError('Unrecognized patient volume path')
            if path.startswith('\\\\?\\Volume{') and path.endswith('}\\'):
                guids.append(path[:-1])
            elif len(path) == 3 and path[1:] == ':\\' and path[0].isalpha():
                if not allow_mounted:
                    raise RuntimeError('Patient has mounted drive letter ' + path[0].upper() +
                                       ':; explicitly approve temporary exclusive dismount first')
                letters.append('\\\\.\\' + path[0].upper() + ':')
            else:
                raise RuntimeError('Unsupported patient volume mount path: ' + path)
        if len(guids) > 1 or len(letters) > 1:
            raise RuntimeError('Ambiguous patient volume paths')
        if guids:
            volume_paths.append(guids[0])
        elif letters:
            volume_paths.append(letters[0])
        else:
            # A partition with no mount letter/GUID is NOT equivalent to a
            # partition-free disk.  It may be RAW, encrypted, or simply
            # invisible through this USB bridge.  Without a volume handle we
            # cannot prove exclusive access.  Fail closed.
            number = partition.get('PartitionNumber', '?')
            kind = str(partition.get('Type') or 'unknown')[:80]
            raise RuntimeError(
                f'Partition {number} ({kind}) has no accessible lockable Windows volume '
                'handle. No write was attempted. Use read-only rescue or a validated '
                'offline recovery environment; do not bypass exclusive access checks.'
            )
    if len(volume_paths) != len(set(volume_paths)):
        raise RuntimeError('Duplicate volume handles detected')
    return volume_paths


class WindowsReadWriter:
    """Win32 physical-drive RW handle with write-through."""

    def __init__(self, device: Device, *, defer_raw_open: bool = False,
                 usb_boot_flash: bool = False) -> None:
        # Boot ISO flashing is a separate, explicitly destructive operation.
        # This narrow USB exception must never unlock HDD repair capabilities.
        if usb_boot_flash:
            if device.bus != 'usb' or not device.path.startswith('\\\\.\\PhysicalDrive'):
                raise PermissionError('Boot-media writer accepts only a verified USB physical disk')
            from .devices import assert_windows_external_write_gate
            assert_windows_external_write_gate(device)
        else:
            release_policy.assert_raw_device_writer_available()
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
        self._device = device
        self.handle = None
        self._volume_handles: list[int] = []
        if not defer_raw_open:
            self.open_raw()

    def open_raw(self) -> None:
        """Open the raw disk only AFTER its volumes are locked for normal repair."""
        if self.handle is not None:
            raise RuntimeError('Raw patient already open')
        access = 0x80000000 | 0x40000000
        flags = 0x80000000  # FILE_FLAG_WRITE_THROUGH
        self.handle = self.kernel.CreateFileW(self._device.path, access, 0, None, 3, flags, None)
        if self.handle == ctypes.c_void_p(-1).value or self.handle is None:
            err = ctypes.get_last_error()
            self.handle = None
            if err == 5:  # ERROR_ACCESS_DENIED
                raise PermissionError(
                    'Windows refused GENERIC_WRITE on the physical drive (WinError 5). '
                    'Re-run DriveRepair from an elevated Administrator terminal for '
                    'in-place refresh. Read-only physical-drive scans may also require '
                    'Administrator access; image-file operations do not.'
                )
            raise ctypes.WinError(err)

    def lock_volumes(self, disk_number: int, *, allow_mounted: bool = False) -> None:
        """Lock every discoverable filesystem volume, including no-letter volumes.

        A mounted directory junction or other unhandled access path is a hard
        stop. Merely checking drive letters does not prove a disk is idle.

        After locks are held, the partition inventory is re-read once. A changed
        partition set or access-path map aborts before the raw disk is opened.
        This is still check-then-use: a race after the recheck remains possible
        until Windows grants exclusive volume ownership for every path.
        """
        from ctypes import wintypes

        # SilentlyContinue: wiped RAW disks have zero partitions / access paths.
        parsed = _windows_partition_inventory(disk_number)
        before = _windows_partition_lock_signature(parsed)
        volume_paths = _windows_lock_paths(parsed, allow_mounted=allow_mounted)
        FSCTL_LOCK_VOLUME = 0x00090018
        FSCTL_DISMOUNT_VOLUME = 0x00090020
        self.kernel.DeviceIoControl.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
        ]
        self.kernel.DeviceIoControl.restype = wintypes.BOOL
        for path in sorted(set(volume_paths)):
            handle = self.kernel.CreateFileW(path, 0x80000000 | 0x40000000, 0x3, None, 3, 0, None)
            if handle == ctypes.c_void_p(-1).value or handle is None:
                raise RuntimeError(f"Cannot open patient volume exclusively: {path}")
            returned = wintypes.DWORD(0)
            if not self.kernel.DeviceIoControl(handle, FSCTL_LOCK_VOLUME, None, 0, None, 0,
                                               ctypes.byref(returned), None):
                self.kernel.CloseHandle(handle)
                raise RuntimeError(f"FSCTL_LOCK_VOLUME failed for {path}: volume is in use")
            self._volume_handles.append(handle)
            if not self.kernel.DeviceIoControl(handle, FSCTL_DISMOUNT_VOLUME, None, 0, None, 0,
                                               ctypes.byref(returned), None):
                raise RuntimeError(f"FSCTL_DISMOUNT_VOLUME failed for {path}")
        # Fail closed if partitions appeared/changed while locks were acquired.
        after = _windows_partition_lock_signature(_windows_partition_inventory(disk_number))
        if after != before:
            raise RuntimeError(
                'Patient partition set changed during volume lock; refusing raw writes'
            )

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
        release_policy.assert_raw_device_writer_available()
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
            # Refuse path re-enumeration between OS handle open and validation.
            # This is only a race guard; it is NOT proof of model/serial identity.
            if os.stat(device.path).st_rdev != st.st_rdev:
                raise RuntimeError('Patient device path changed while opening writer')
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


def open_device_readwrite(device: Device, *, auto_lock_volumes: bool = False) -> ReadWriter:
    release_policy.assert_raw_device_writer_available()
    if sys.platform == "win32":
        media = WindowsReadWriter(device, defer_raw_open=True)
        number = int(device.path.rsplit("PhysicalDrive", 1)[-1])
        try:
            # Acquire exclusive filesystem locks before opening the raw disk.
            # A mounted letter is not intrinsically busy; open files cause the
            # lock to fail, in which case all handles are released unchanged.
            media.lock_volumes(number, allow_mounted=auto_lock_volumes)
            media.open_raw()
            return media
        except BaseException:
            media.close()
            raise
    if sys.platform == "darwin":
        raise RuntimeError("Raw media refresh is disabled on macOS until exclusive locking is implemented and validated")
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
        raise RuntimeError(
            "Patient identity changed (model/size/serial/bus/path); "
            "USB location/topology alone is ignored"
        )
    if expected.size_bytes != observed.size_bytes or expected.sector_size != observed.sector_size:
        raise RuntimeError("Patient capacity or sector size changed")


def assert_patient_idle_windows(device: Device, *, allow_locked_volume: bool = False) -> None:
    """Refuse refresh when Windows reports a drive letter on the patient.

    A wiped RAW disk with no partitions is idle — Get-Partition failing with
    "no MSFT_Partition" must not block full-surface write verification.
    """
    if sys.platform != "win32":
        return
    if allow_locked_volume:
        # This is NOT a bypass of exclusive access. The actual write-open MUST
        # successfully lock + dismount every volume before any patient writes.
        # Only caller-authorized external disks are eligible.
        return
    import subprocess
    number = int(device.path.rsplit("PhysicalDrive", 1)[-1])
    # SilentlyContinue: unpartitioned/RAW patients are a valid wipe+refresh target.
    script = (
        f"$p = @(Get-Partition -DiskNumber {number} -ErrorAction SilentlyContinue); "
        "$letters = @($p | Where-Object { $_.DriveLetter } | ForEach-Object { [string]$_.DriveLetter }); "
        "if ($letters.Count -eq 0) { '[]' } else { $letters | ConvertTo-Json -Compress }"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, timeout=25,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Unable to verify patient mount state: {exc}") from exc
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or b"").decode("utf-8-sig", errors="replace").strip()
        raise RuntimeError(f"Unable to verify patient mount state: {err or completed.returncode}")
    raw = completed.stdout.decode("utf-8-sig").strip()
    if not raw or raw == "null":
        return
    parsed = json.loads(raw)
    letters = [parsed] if isinstance(parsed, str) else list(parsed or [])
    # Filter empty strings PowerShell may emit for blank DriveLetter fields.
    letters = [str(item) for item in letters if str(item).strip()]
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
    # Persist the directory entry before recording SAVED/WRITING in meta.json.
    if os.name == "posix":
        dirfd = os.open(os.path.dirname(path), os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)


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
    sector: int,
    samples: int,
    slow_multiplier: float,
    auto_escalate: bool = True,
    progress: Callable[[dict], None] | None = None,
    stop_requested: Callable[[], bool] | None = None,
) -> tuple[list[tuple[int, int]], dict]:
    """Return slow-but-readable regions plus probe telemetry for Adaptive Refresh.

    Cooperative stop is checked between probes/escalations. An already-blocked
    OS read cannot be interrupted from user-space.
    """
    blocks = max(1, (size + chunk - 1) // chunk)
    n = min(samples, blocks)
    timings: list[tuple[int, int, float]] = []
    probe_failures = 0
    escalations = 0
    mechanical_alerts = 0
    extreme_streak = 0
    running_median = None
    stopped = False

    def emit(**kwargs) -> None:
        if progress:
            progress(kwargs)

    def read_timed(offset: int, length: int) -> tuple[bytes | None, float, str | None]:
        started = time.perf_counter()
        try:
            data = media.read_at(offset, length)
            elapsed = time.perf_counter() - started
            if len(data) != length:
                return None, elapsed, "media_or_io"
            return data, elapsed, None
        except OSError as exc:
            return None, time.perf_counter() - started, _classify_os_error(exc)

    for i in range(n):
        if stop_requested is not None and stop_requested():
            stopped = True
            break
        index = (i * (blocks - 1) // (n - 1)) if n > 1 else 0
        offset = index * chunk
        length = min(chunk, size - offset)
        if length <= 0:
            continue
        data, elapsed, err = read_timed(offset, length)
        if running_median is None and timings:
            running_median = sorted(t for _, _, t in timings)[len(timings) // 2]
        elif timings:
            times_so_far = sorted(t for _, _, t in timings)
            running_median = times_so_far[len(times_so_far) // 2]
        thr_guess = None
        if running_median is not None:
            thr_guess = max(running_median * slow_multiplier, running_median + 1e-6)
        mechanical_fail = False
        if thr_guess and elapsed >= max(thr_guess * 5, 1.0):
            extreme_streak += 1
        else:
            extreme_streak = 0
        if extreme_streak >= 3:
            mechanical_fail = True
            mechanical_alerts += 1
            extreme_streak = 0
        emit(
            status="probing",
            phase="probe",
            probe_index=i + 1,
            probe_total=n,
            offset=offset,
            latency_s=elapsed,
            median_s=running_median,
            threshold_s=thr_guess,
            failed=data is None,
            error_class=err,
            mechanical_fail=mechanical_fail,
            message=f"Probe {i + 1}/{n} @ {_fmt_offset(offset)} ({elapsed * 1000:.0f} ms)",
            force=True,
        )
        if data is None:
            probe_failures += 1
            if auto_escalate and length > sector * 8:
                if stop_requested is not None and stop_requested():
                    stopped = True
                    break
                added, escalate_stopped = _escalate_region(
                    media, offset, length, sector, timings, emit,
                    stop_requested=stop_requested,
                )
                escalations += added
                if escalate_stopped:
                    stopped = True
                    break
            continue
        timings.append((offset, length, elapsed))
        if auto_escalate and thr_guess and elapsed >= max(thr_guess * 3, 0.2):
            if stop_requested is not None and stop_requested():
                stopped = True
                break
            added, escalate_stopped = _escalate_region(
                media, offset, length, sector, timings, emit,
                stop_requested=stop_requested,
            )
            escalations += added
            if escalate_stopped:
                stopped = True
                break

    if stopped:
        return [], {
            "adaptive_samples_requested": samples,
            "adaptive_samples_readable": len(timings),
            "adaptive_probe_failures": probe_failures,
            "adaptive_targets": 0,
            "adaptive_escalations": escalations,
            "adaptive_mechanical_alerts": mechanical_alerts,
            "adaptive_median_seconds": None,
            "adaptive_threshold_seconds": None,
            "adaptive_probe_stopped": True,
        }
    if not timings:
        return [], {
            "adaptive_samples_requested": samples,
            "adaptive_samples_readable": 0,
            "adaptive_probe_failures": probe_failures,
            "adaptive_targets": 0,
            "adaptive_escalations": escalations,
            "adaptive_mechanical_alerts": mechanical_alerts,
            "adaptive_median_seconds": None,
            "adaptive_threshold_seconds": None,
        }
    times = sorted(t for _, _, t in timings)
    median = times[len(times) // 2]
    threshold = max(median * slow_multiplier, median + 1e-6)
    # Deduplicate targets (escalation may add overlapping finer ranges).
    merged: dict[int, int] = {}
    for offset, length, latency in timings:
        if latency >= threshold:
            merged[offset] = max(merged.get(offset, 0), length)
    targets = sorted(merged.items())
    return targets, {
        "adaptive_samples_requested": samples,
        "adaptive_samples_readable": len(timings),
        "adaptive_probe_failures": probe_failures,
        "adaptive_targets": len(targets),
        "adaptive_escalations": escalations,
        "adaptive_mechanical_alerts": mechanical_alerts,
        "adaptive_median_seconds": round(median, 6),
        "adaptive_threshold_seconds": round(threshold, 6),
    }


def _fmt_offset(offset: int) -> str:
    if offset >= 1024**4:
        return f"{offset / 1024**4:.2f} TiB"
    if offset >= 1024**3:
        return f"{offset / 1024**3:.2f} GiB"
    if offset >= 1024**2:
        return f"{offset / 1024**2:.1f} MiB"
    return f"{offset} B"


def _escalate_region(
    media: ReadWriter,
    offset: int,
    length: int,
    sector: int,
    timings: list[tuple[int, int, float]],
    emit: Callable[..., None],
    stop_requested: Callable[[], bool] | None = None,
) -> tuple[int, bool]:
    """Deeper subdivision probe for slow/failed zones; adds readable sub-timings.

    Returns (added_readable_subsamples, stopped). Stop is cooperative between
    sub-reads only; a blocked OS read is not interruptible here.
    """
    parts = 4
    sub = length // parts
    sub -= sub % sector
    if sub < sector * 8:
        return 0, False
    emit(
        status="escalating",
        phase="escalate",
        offset=offset,
        message=f"Auto-escalate deeper test @ {_fmt_offset(offset)} ({parts} sub-reads)",
        force=True,
    )
    added = 0
    for i in range(parts):
        if stop_requested is not None and stop_requested():
            return added, True
        off = offset + i * sub
        ln = sub if i < parts - 1 else (offset + length - off)
        ln -= ln % sector
        if ln < sector:
            continue
        started = time.perf_counter()
        try:
            data = media.read_at(off, ln)
            elapsed = time.perf_counter() - started
            if len(data) != ln:
                emit(status="probing", offset=off, failed=True, latency_s=elapsed,
                     error_class="media_or_io", force=True,
                     message=f"Escalate sub-read short @ {_fmt_offset(off)}")
                continue
            timings.append((off, ln, elapsed))
            added += 1
            emit(status="probing", offset=off, latency_s=elapsed, failed=False, force=True,
                 message=f"Escalate sub-read ok @ {_fmt_offset(off)} ({elapsed * 1000:.0f} ms)")
        except OSError as exc:
            emit(status="probing", offset=off, failed=True, latency_s=time.perf_counter() - started,
                 error_class=_classify_os_error(exc), force=True,
                 message=f"Escalate sub-read error @ {_fmt_offset(off)}")
    return added, False


class JournalStore:
    """Journal for current region; memory backend never touches a filesystem.

    `memory` is **not durable**. Crash or power loss destroys the preimage;
    only use for explicitly authorized last-resort work, never for resume.
    `ramdisk` has disk-like transactional semantics on verified tmpfs, which
    can survive application crashes but not loss of host RAM.
    """

    def __init__(self, journal_dir: str, backend: str) -> None:
        if backend not in {"disk", "hybrid", "memory", "ramdisk"}:
            raise ValueError("journal backend must be disk, hybrid, memory, or ramdisk")
        self.backend = backend
        self.journal_dir = os.path.abspath(journal_dir)
        self.meta_path = os.path.join(self.journal_dir, "meta.json")
        self.blob_path = os.path.join(self.journal_dir, "region.bin")
        self._region: bytes | None = None
        self._meta: dict | None = None

    def prepare_new(self) -> None:
        if self.backend == "memory":
            return  # zero filesystem artifacts, even metadata or lock files
        # An empty directory is fine (operators often mkdir the path first).
        # Refuse only when a prior journal artifact is present.
        if os.path.lexists(self.journal_dir):
            if not os.path.isdir(self.journal_dir):
                raise FileExistsError("Refresh journal path exists and is not a directory")
            leftover = [
                name for name in os.listdir(self.journal_dir)
                if name not in {'.', '..'}
            ]
            if leftover:
                raise FileExistsError("Refresh journal already exists; use --resume")
        else:
            os.makedirs(self.journal_dir, mode=0o700)

    def save_meta(self, meta: dict) -> None:
        self._meta = dict(meta)
        if self.backend == "memory":
            return  # Process-local only; never claim a restart checkpoint exists.
        _state_save(self.meta_path, {**meta, "journal_backend": self.backend,
                                     "region_in_ram": self.backend == "hybrid"})

    def save_region(self, data: bytes) -> None:
        self._region = data
        if self.backend in {"disk", "ramdisk"}:
            _atomic_write_bytes(self.blob_path, data)
        # hybrid/memory: keep bytes in RAM only for speed.

    def load_region(self, length: int, digest: str) -> bytes:
        if self._region is not None:
            data = self._region
        elif os.path.isfile(self.blob_path):
            # Disk fallback enables resume after process restart (disk backend, or
            # hybrid/memory if a prior durable blob exists).
            with open(self.blob_path, "rb") as handle:
                data = handle.read()
            self._region = data
        else:
            raise RuntimeError(
                "Region journal bytes unavailable (RAM journal lost or missing region.bin). "
                "Cannot safely resume an in-flight rewrite."
            )
        if len(data) != length or _sha256(data) != digest:
            raise RuntimeError("Journal region blob failed integrity check; refusing resume")
        return data

    def clear_region(self) -> None:
        self._region = None
        if self.backend == "memory":
            return
        if os.path.isfile(self.blob_path):
            os.unlink(self.blob_path)

    def cleanup(self) -> None:
        self.clear_region()
        if self.backend == "memory":
            return
        if os.path.isdir(self.journal_dir):
            for name in os.listdir(self.journal_dir):
                try:
                    os.unlink(os.path.join(self.journal_dir, name))
                except OSError:
                    pass
            try:
                os.rmdir(self.journal_dir)
            except OSError:
                pass


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


def _commit_transaction(store: JournalStore, meta: dict, *, verified: bool) -> None:
    """Commit exactly once, with progress durable before deleting the saved bytes."""
    tx = meta["transaction"]
    if not tx or tx["state"] != STATE_VERIFIED:
        raise RuntimeError("Cannot commit a transaction that is not verified")
    offset, length = int(tx["offset"]), int(tx["length"])
    if meta["mode"] == "full":
        if int(meta["cursor"]) != offset:
            raise RuntimeError("Full-surface journal cursor no longer matches transaction")
        meta["cursor"] = offset + length
    else:
        queue = meta.get("queue") or []
        if not queue or list(map(int, queue[0])) != [offset, length]:
            raise RuntimeError("Adaptive journal queue no longer matches transaction")
        meta["queue"] = queue[1:]
    meta["rewritten_bytes"] = int(meta["rewritten_bytes"]) + length
    if verified:
        meta["verified_bytes"] = int(meta["verified_bytes"]) + length
        if meta.get("mode") == "targeted":
            # Hash of the *original* double-read preimage, persisted atomically
            # with COMMITTED state. Allows independent post-repair comparison
            # using a fresh readonly handle without retaining patient bytes.
            records = meta.setdefault("committed_digest_records", [])
            record = [offset, length, str(tx["sha256"])]
            if record not in records:
                records.append(record)
            if len(records) > 256:
                raise RuntimeError("Targeted digest journal limit exceeded")
    tx["state"] = STATE_COMMITTED
    store.save_meta(meta)  # COMMITTED persists progress before deletion.
    store.clear_region()
    meta["transaction"] = None
    store.save_meta(meta)


def _recover_interrupted_transaction(media: ReadWriter, store: JournalStore, meta: dict,
                                     identity_check: Callable[[], None] | None = None,
                                     pre_write_check: Callable[[], None] | None = None) -> dict:
    """Fail closed if a transaction cannot be restored; never lose its journal."""
    tx = meta.get("transaction")
    if not tx:
        return meta
    state = tx.get("state")
    if state == STATE_COMMITTED:
        # Accounting already persisted with COMMITTED. Blob is no longer needed.
        store.clear_region()
        meta["transaction"] = None
        store.save_meta(meta)
        return meta
    offset, length = int(tx["offset"]), int(tx["length"])
    data = store.load_region(length, tx["sha256"])
    if identity_check:
        identity_check()
    if state == STATE_VERIFIED:
        # A crash may have occurred before moving the cursor. Revalidate before commit.
        if media.read_at(offset, length) == data:
            _commit_transaction(store, meta, verified=bool(meta["verify"]))
            return meta
        # The region changed: fall through to restore with the preserved bytes.
    elif state not in {STATE_SAVED, STATE_WRITING}:
        raise RuntimeError(f"Unknown transaction state {state!r}")
    if state in {STATE_WRITING, STATE_VERIFIED}:
        if pre_write_check:
            pre_write_check()
        # Previous write may be torn. Keep the saved bytes until confirmed restored.
        _write_all_at(media, offset, data)
        if media.read_at(offset, length) != data:
            raise RuntimeError("Interrupted region restoration failed verification; journal retained")
    tx["state"] = STATE_SAVED
    store.save_meta(meta)
    return meta


def _validate_resume_transaction(meta: dict, *, size: int, sector: int,
                                 chunk: int, mode: str) -> None:
    """Reject malformed journal coordinates before any patient write.

    Journal files are operator-visible state, not an authorization boundary.
    A damaged or hand-edited transaction must never turn into an unchecked
    offset passed to a physical writer during resume.
    """
    transaction = meta.get("transaction")
    if transaction is None:
        return
    if not isinstance(transaction, dict):
        raise ValueError("Malformed refresh journal transaction")
    state = transaction.get("state")
    if state not in {STATE_SAVED, STATE_WRITING, STATE_VERIFIED, STATE_COMMITTED}:
        raise ValueError("Malformed refresh journal transaction state")
    offset = transaction.get("offset")
    length = transaction.get("length")
    digest = transaction.get("sha256")
    if (type(offset) is not int or type(length) is not int or
            offset < 0 or length <= 0 or offset % sector or length % sector or
            length > chunk or offset + length > size or
            not isinstance(digest, str) or len(digest) != 64 or
            any(c not in '0123456789abcdef' for c in digest)):
        raise ValueError("Malformed or out-of-bounds refresh journal transaction")
    if mode == "full":
        cursor = meta.get("cursor")
        if (state != STATE_COMMITTED and
                (type(cursor) is not int or cursor != offset)):
            raise ValueError("Refresh journal cursor does not match its transaction")
    else:
        queue = meta.get("queue")
        if state != STATE_COMMITTED:
            if (not isinstance(queue, list) or not queue or
                    queue[0] != [offset, length]):
                raise ValueError("Refresh journal queue does not match its transaction")


def _stop_with_journal(store: JournalStore, meta: dict, status: str,
                       *, error: str | None = None) -> str:
    """Stop on write/verify failure; DO NOT discard the only surviving original bytes."""
    meta["status"] = status
    if error:
        meta["last_error_class"] = error
    store.save_meta(meta)
    return status


def refresh_media(
    media: ReadWriter,
    *,
    size: int,
    sector: int,
    source_token: str,
    journal: str,
    chunk: int = 1024 * 1024,
    mode: str = "adaptive",
    targets: list[tuple[int, int]] | None = None,
    verify: bool = True,
    resume: bool = False,
    max_errors: int = 4096,
    consistency_reads: int = 2,
    adaptive_samples: int = 256,
    slow_multiplier: float = 2.0,
    journal_backend: str = "disk",
    auto_escalate: bool = True,
    progress: Callable[[dict], None] | None = None,
    identity_check: Callable[[], None] | None = None,
    pre_write_check: Callable[[], None] | None = None,
    stop_requested: Callable[[], bool] | None = None,
) -> dict:
    if mode not in {"adaptive", "full", "targeted"}:
        raise ValueError("mode must be adaptive, full or targeted")
    if mode != "targeted" and targets is not None:
        raise ValueError("Explicit targets require targeted mode")
    if size <= 0 or sector <= 0 or size % sector or chunk < sector or chunk % sector:
        raise ValueError("Invalid size/sector/chunk alignment for refresh")
    if not 1 <= max_errors <= 100000 or consistency_reads < 2:
        raise ValueError("Invalid max_errors or consistency_reads")
    if journal_backend == "memory" and resume:
        raise ValueError("Process-RAM journal cannot resume after exit; its original bytes are lost")

    # Validate EVERY offset before creating the journal or opening a write
    # transaction. Adjacent targets are permitted; overlaps and out-of-bounds
    # requests are rejected rather than normalized into broader writes.
    checked_targets = None
    if targets is not None:
        checked_targets = []
        previous_end = 0
        if len(targets) > 256:
            raise ValueError("Too many targeted regions; subdivide the job")
        for offset, length in targets:
            if (type(offset) is not int or type(length) is not int or
                    offset < 0 or length <= 0 or offset % sector or length % sector or
                    offset < previous_end or offset + length > size or length > chunk):
                raise ValueError("Invalid, overlapping, or unaligned targeted region")
            checked_targets.append([offset, length])
            previous_end = offset + length
    if mode == "targeted" and not resume and not checked_targets:
        raise ValueError("New targeted refresh requires nonempty verified targets")

    target_digest = (_sha256(json.dumps(checked_targets, separators=(",", ":")).encode())
                     if checked_targets is not None else None)
    store = JournalStore(journal, journal_backend)
    started = time.monotonic()
    probe_started = started
    probe_elapsed = 0.0

    if resume:
        if not os.path.isdir(store.journal_dir) or not os.path.isfile(store.meta_path):
            raise FileNotFoundError("Cannot resume; rolling journal missing")
        with open(store.meta_path, encoding="utf-8") as handle:
            meta = json.loads(handle.read())
        if meta.get("schema") != 2 or meta.get("operation") != "media_refresh_rolling":
            raise ValueError("Journal is not a rolling media_refresh state directory")
        if meta.get("source_token") != source_token or meta.get("size") != size:
            raise RuntimeError("Journal does not match this media identity/size")
        if meta.get("sector") != sector or meta.get("chunk") != chunk or meta.get("mode") != mode:
            raise RuntimeError("Journal sector/chunk/mode does not match this run")
        if meta.get("verify") != verify or meta.get("consistency_reads") != consistency_reads:
            raise RuntimeError("Verification/consistency settings changed on resume")
        if meta.get("journal_backend") not in {None, journal_backend}:
            raise RuntimeError("Journal backend changed on resume")
        if mode == "targeted" and (meta.get("target_digest") is None or
                                    target_digest is not None and meta["target_digest"] != target_digest):
            raise RuntimeError("Target set differs from the interrupted journal")
        _validate_resume_transaction(meta, size=size, sector=sector,
                                     chunk=chunk, mode=mode)
        meta = _recover_interrupted_transaction(media, store, meta, identity_check, pre_write_check)
    else:
        store.prepare_new()
        meta = _default_meta(
            source_token=source_token, size=size, sector=sector, chunk=chunk,
            mode=mode, verify=verify, consistency_reads=consistency_reads,
        )
        meta["journal_backend"] = journal_backend
        if mode == "targeted":
            meta["queue"] = checked_targets
            meta["target_digest"] = target_digest
            meta["target_count"] = len(checked_targets)
        if mode == "adaptive":
            probe_started = time.monotonic()
            targets, probe_stats = _probe_adaptive_targets(
                media, size=size, chunk=chunk, sector=sector, samples=adaptive_samples,
                slow_multiplier=slow_multiplier, auto_escalate=auto_escalate,
                progress=progress, stop_requested=stop_requested,
            )
            probe_elapsed = round(time.monotonic() - probe_started, 3)
            meta["queue"] = [[offset, length] for offset, length in targets]
            meta.update(probe_stats)
            meta["probe_elapsed_seconds"] = probe_elapsed
        elif mode == "full":
            meta["queue"] = None
        store.save_meta(meta)

    status = "completed"
    if mode == "adaptive" and meta.get("adaptive_probe_stopped"):
        # Stop during probing: no rewrite queue, no writes after stop.
        status = "stopped_at_safe_boundary"
    elif mode == "adaptive" and int(meta.get("adaptive_probe_failures") or 0):
        # Do not attempt destructive maintenance when the preliminary survey
        # already encountered unreadable regions. Rescue first.
        status = "aborted_probe_read_errors"
    refresh_index = 0
    refresh_total = len(meta.get("queue") or []) if mode in {"adaptive", "targeted"} else max(
        1, (size + chunk - 1) // chunk
    )

    def save() -> None:
        store.save_meta(meta)
        if progress:
            event = dict(meta)
            event["status"] = "refreshing"
            event["phase"] = "refresh"
            event["refresh_index"] = refresh_index
            event["refresh_total"] = refresh_total
            progress(event)

    def next_region() -> tuple[int, int] | None:
        if mode in {"adaptive", "targeted"}:
            queue = meta.get("queue") or []
            return (int(queue[0][0]), int(queue[0][1])) if queue else None
        cursor = int(meta["cursor"])
        if cursor >= size:
            return None
        length = min(chunk, size - cursor)
        length -= length % sector
        return (cursor, length) if length else None

    def skip_region(offset: int, length: int, *, inconsistent: bool = False) -> None:
        key = "inconsistent_ranges" if inconsistent else "skipped_ranges"
        meta[key] = _merge_ranges(list(meta.get(key) or []) + [[offset, length]])
        if mode == "full":
            meta["cursor"] = offset + length
        else:
            queue = meta.get("queue") or []
            if not queue or list(map(int, queue[0])) != [offset, length]:
                raise RuntimeError("Adaptive queue mismatch while skipping region")
            meta["queue"] = queue[1:]
        save()

    try:
        while status == "completed":
            # Only stop between committed transactions. Never abandon a SAVED
            # or WRITING region (especially with a volatile RAM journal).
            if stop_requested is not None and stop_requested() and not meta.get("transaction"):
                status = "stopped_at_safe_boundary"
                break
            if identity_check:
                identity_check()
            tx = meta.get("transaction")
            if tx:
                if tx.get("state") != STATE_SAVED:
                    raise RuntimeError("Unexpected transaction state after resume")
                offset, length = int(tx["offset"]), int(tx["length"])
                data = store.load_region(length, tx["sha256"])
                if identity_check:
                    identity_check()
                if pre_write_check:
                    pre_write_check()
                tx["state"] = STATE_WRITING
                save()  # Durable WRITING state before patient mutation.
                try:
                    _write_all_at(media, offset, data)
                    # Always read back: even --no-verify must detect obvious errors.
                    observed = media.read_at(offset, length)
                    if observed != data:
                        raise OSError(errno.EIO, "Post-write readback mismatch")
                except (OSError, RuntimeError) as exc:
                    meta["failed_write_attempts"] = int(meta["failed_write_attempts"]) + 1
                    if store.backend == "memory":
                        # With no durable journal a return to the GUI destroys the
                        # only preimage. Make ONE bounded attempt to put it back
                        # while it still exists in RAM, and verify that attempt.
                        try:
                            if pre_write_check:
                                pre_write_check()
                            _write_all_at(media, offset, data)
                            if media.read_at(offset, length) != data:
                                raise OSError(errno.EIO, "Rollback readback mismatch")
                        except (OSError, RuntimeError) as restore_error:
                            status = _stop_with_journal(
                                store, meta, "critical_volatile_rollback_failed",
                                error=f"Initial error: {exc}; restoration: {restore_error}",
                            )
                        else:
                            meta["transaction"] = None
                            status = _stop_with_journal(
                                store, meta, "aborted_volatile_region_restored",
                                error=f"Region restored and verified after error: {exc}",
                            )
                    else:
                        status = _stop_with_journal(
                            store, meta, "aborted_write_or_verify_error", error=str(exc)
                        )
                    if progress:
                        progress({"status": status, "phase": "refresh", "offset": offset,
                                  "failed": True, "force": True,
                                  "message": "Write/readback failed; original bytes retained in journal"})
                    break
                tx["state"] = STATE_VERIFIED
                save()
                _commit_transaction(store, meta, verified=verify)
                refresh_index += 1
                save()
                continue

            region = next_region()
            if region is None:
                break
            offset, length = region
            try:
                data = _read_consistent(media, offset, length, consistency_reads)
            except RuntimeError as exc:
                if str(exc) != "inconsistent_reads":
                    raise
                skip_region(offset, length, inconsistent=True)
                continue
            except OSError as exc:
                meta["failed_read_attempts"] = int(meta["failed_read_attempts"]) + 1
                meta["last_error_class"] = _classify_os_error(exc)
                skip_region(offset, length)
                if exc.errno in _FATAL:
                    status = "aborted_device_or_access_error"
                    break
                if int(meta["failed_read_attempts"]) + int(meta["failed_write_attempts"]) >= max_errors:
                    status = "aborted_error_limit"
                    break
                continue

            # Save original bytes BEFORE any patient write. Disk and checked
            # tmpfs journals may survive an app crash; process RAM NEVER does.
            store.save_region(data)
            meta["transaction"] = {
                "state": STATE_SAVED,
                "offset": offset,
                "length": length,
                "sha256": _sha256(data),
            }
            save()
    finally:
        pass

    if status == "completed":
        if meta.get("skipped_ranges") or meta.get("inconsistent_ranges"):
            status = "completed_with_skips_or_verify_failures"
        elif int(meta.get("adaptive_probe_failures") or 0):
            status = "completed_with_probe_errors"
        if meta.get("transaction"):
            status = "interrupted"
        elif mode == "full" and int(meta["cursor"]) < size:
            status = "interrupted"
        elif mode == "adaptive" and (meta.get("queue") or []):
            status = "interrupted"

    meta["status"] = status
    meta["elapsed_seconds"] = round(time.monotonic() - started, 3)
    save()
    result = {
        "schema": 2,
        "operation": "media_refresh_rolling",
        "status": meta["status"],
        "mode": mode,
        "size": size,
        "sector": sector,
        "chunk": chunk,
        "source_token": source_token,
        "journal": None if store.backend == "memory" else store.journal_dir,
        "journal_backend": journal_backend,
        "volatile_ram_only": journal_backend == "memory",
        # Hybrid keeps the in-flight preimage in RAM: metadata may resume
        # at committed boundaries, but cannot restore a torn current region.
        "resume_possible_after_exit": journal_backend in {'disk', 'ramdisk'},
        "resume_at_committed_boundary": journal_backend != 'memory',
        "recover_inflight_region_after_crash": journal_backend == 'disk',
        "preimage_durable": journal_backend == 'disk',
        "cursor": meta.get("cursor"),
        "queue_remaining": len(meta.get("queue") or []),
        "target_count": meta.get("target_count", 0),
        "rewritten_bytes": meta["rewritten_bytes"],
        "verified_bytes": meta["verified_bytes"],
        "committed_digest_records": meta.get("committed_digest_records") or [],
        "skipped_ranges": meta.get("skipped_ranges") or [],
        "inconsistent_ranges": meta.get("inconsistent_ranges") or [],
        "failed_read_attempts": meta["failed_read_attempts"],
        "failed_write_attempts": meta["failed_write_attempts"],
        "transaction": meta.get("transaction"),
        "last_error_class": meta.get("last_error_class"),
        "verify": verify,
        "consistency_reads": consistency_reads,
        "elapsed_seconds": meta["elapsed_seconds"],
        "probe_elapsed_seconds": meta.get("probe_elapsed_seconds", probe_elapsed),
        "total_elapsed_seconds": round(time.monotonic() - started, 3),
        "notes": meta["notes"],
        "windows_admin_required": sys.platform == "win32",
    }
    for key in (
        "adaptive_samples_requested", "adaptive_samples_readable", "adaptive_probe_failures",
        "adaptive_targets", "adaptive_median_seconds", "adaptive_threshold_seconds",
        "adaptive_escalations", "adaptive_mechanical_alerts",
    ):
        if key in meta:
            result[key] = meta[key]
    return result

