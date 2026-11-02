"""Conservative external-disk discovery via built-in host operating system tools.

Discovery is informational and is re-run immediately before raw device access.
The scanner only accepts discovered external *whole disks*, never arbitrary paths.
"""

from __future__ import annotations

import hashlib
import json
import plistlib
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Device:
    id: str
    path: str
    model: str
    size_bytes: int
    sector_size: int
    bus: str
    serial: str = ""
    location: str = ""
    provenance: str = "native"

    @property
    def fingerprint(self) -> str:
        # Location/topology strings (especially USB) can flap between discovery
        # calls on the same physical disk. Identity must ignore them or mid-job
        # rechecks abort healthy rescues with "device changed".
        data = (self.id, self.path, self.model, str(self.size_bytes),
                str(self.sector_size), self.bus, self.serial)
        return hashlib.sha256("\0".join(data).encode("utf-8")).hexdigest()

    @property
    def scan_resume_identity(self) -> str | None:
        """Stable READ-ONLY scan identity across USB port / PhysicalDrive renumbering.

        Not a physical-write authority. A USB bridge might hide or reuse serials;
        only use for scan metadata and require a meaningful serial on resume.
        """
        serial = self.serial.strip()
        if len(serial) < 4 or serial.lower() in {'unknown', 'none', 'null', 'n/a', 'unavailable'}:
            return None
        parts = (self.model.strip().casefold(), serial.casefold(),
                 str(self.size_bytes), str(self.sector_size), self.bus.strip().casefold())
        return hashlib.sha256("\0".join(parts).encode('utf-8')).hexdigest()

    def public(self) -> dict:
        """Do not include full hardware serial numbers in routine output."""
        return {
            "id": self.id, "model": self.model, "size_bytes": self.size_bytes,
            "sector_size": self.sector_size, "bus": self.bus,
            "serial_suffix": ("***" + self.serial[-4:]) if self.serial else "unavailable",
            "location": self.location or "not reported",
            "discovery": self.provenance,
            "identity_hint": self.fingerprint[:12],
            "resume_hint": self.scan_resume_identity[:12] if self.scan_resume_identity else None,
        }


def _kill_process_tree(pid: int) -> None:
    """Best-effort Windows process-tree kill so timed-out Get-Disk cannot wedge Storage."""
    if pid <= 0:
        return
    if sys.platform == 'win32':
        try:
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        return
    try:
        import os
        import signal
        os.kill(pid, signal.SIGKILL)
    except (OSError, ImportError):
        pass


def _run(command: list[str], timeout: float = 25) -> bytes:
    proc: subprocess.Popen[bytes] | None = None
    try:
        proc = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _kill_process_tree(proc.pid)
            try:
                proc.kill()
            except OSError:
                pass
            try:
                proc.communicate(timeout=3)
            except (subprocess.TimeoutExpired, OSError):
                pass
            raise RuntimeError(
                f"Device discovery failed ({command[0]}): Command {command!r} "
                f"timed out after {timeout} seconds"
            ) from exc
        if proc.returncode:
            detail = (stderr or b'').decode('utf-8', 'replace').strip()
            raise RuntimeError(
                f"Device discovery failed ({command[0]}): exit {proc.returncode}"
                + (f": {detail}" if detail else "")
            )
        return stdout
    except FileNotFoundError as exc:
        raise RuntimeError(f"Device discovery failed ({command[0]}): {exc}") from exc
    finally:
        if proc is not None and proc.poll() is None:
            _kill_process_tree(proc.pid)


def _bool(value: object) -> bool:
    return value is True or str(value).lower() in {"true", "1", "yes"}


def _positive_int(value: object, default: int = 0) -> int:
    try:
        v = int(value)  # type: ignore[arg-type]
        return v if v > 0 else default
    except (ValueError, TypeError, OverflowError):
        return default


def _linux_disks(run: Callable[[list[str]], bytes], *, include_internal: bool) -> list[Device]:
    command = ["lsblk", "--json", "--bytes", "--nodeps", "--output",
               "PATH,TYPE,TRAN,HOTPLUG,RM,SIZE,LOG-SEC,MODEL,SERIAL,WWN,HCTL"]
    records = json.loads(run(command).decode("utf-8"))["blockdevices"]
    devices: list[Device] = []
    for record in records:
        if record.get("type") != "disk":
            continue
        bus = str(record.get("tran") or "unknown").lower()
        # Hotplug alone may describe an *internal* SATA port. Be conservative.
        external = (bus in {"usb", "sbp", "firewire", "thunderbolt", "mmc", "sd"}
                    or _bool(record.get("rm")))
        path = str(record.get("path") or "")
        size = _positive_int(record.get("size"))
        sector = _positive_int(record.get("log-sec"))
        if (not external and not include_internal) or not re.fullmatch(r"/dev/[a-zA-Z0-9._+-]+", path):
            continue
        if not size or not sector or size % sector:
            continue
        devices.append(Device("linux:" + path, path,
                              str(record.get("model") or "Unknown disk").strip(),
                              size, sector, bus, str(record.get("serial") or "").strip(),
                              ("HCTL " + str(record["hctl"])) if record.get("hctl") else "", "lsblk"))
    return devices


def linux_devices(run: Callable[[list[str]], bytes] = _run) -> list[Device]:
    """Externally connected whole disks only (safe desktop default)."""
    return _linux_disks(run, include_internal=False)


def linux_all_devices(run: Callable[[list[str]], bytes] = _run) -> list[Device]:
    """Linux offline-recovery inventory. Caller must check mounts/holders."""
    return _linux_disks(run, include_internal=True)


def select_linux_any_disk(identifier: str,
                          discover: Callable[[], list[Device]] = linux_all_devices) -> Device:
    matches = [d for d in discover() if d.id == identifier]
    if len(matches) != 1 or not matches[0].serial:
        raise ValueError("Disk absent, ambiguous or missing a stable serial; use list-all-linux")
    return matches[0]


def macos_devices(run: Callable[[list[str]], bytes] = _run) -> list[Device]:
    raw = plistlib.loads(run(["diskutil", "list", "-plist", "external", "physical"]))
    devices: list[Device] = []
    for entry in raw.get("AllDisksAndPartitions", []):
        disk = str(entry.get("DeviceIdentifier") or "")
        if not re.fullmatch(r"disk\d+", disk):
            continue
        info = plistlib.loads(run(["diskutil", "info", "-plist", disk]))
        # Mandatory authoritative external/whole-disk checks; fail closed.
        if info.get("Internal") is not False or info.get("WholeDisk") is not True:
            continue
        if info.get("DeviceIdentifier") != disk:
            continue
        size = _positive_int(info.get("TotalSize"))
        sector = _positive_int(info.get("DeviceBlockSize"))
        if not size or not sector or size % sector:
            continue
        devices.append(Device("macos:" + disk, "/dev/r" + disk,
                              str(info.get("MediaName") or "External disk"),
                              size, sector, str(info.get("Protocol") or "external"),
                              str(info.get("DiskUUID") or info.get("MediaUUID") or ""),
                              str(info.get("DeviceLocation") or "").strip(), "diskutil"))
    return devices


def _invoke(run: Callable[..., bytes], command: list[str], timeout: float) -> bytes:
    try:
        return run(command, timeout=timeout)
    except TypeError as exc:
        if "unexpected keyword argument 'timeout'" not in str(exc):
            raise
        return run(command)


def _windows_devices_from_get_disk(run: Callable[..., bytes], number: int | None = None) -> list[Device]:
    # Preferred path when Storage cmdlets are healthy.
    prefix = ("Get-Disk -Number " + str(number) + " -ErrorAction Stop"
              if number is not None else "Get-Disk")
    script = (prefix + " | Select-Object Number,FriendlyName,SerialNumber,UniqueId,"
              "Size,LogicalSectorSize,BusType,IsBoot,IsSystem,IsOffline,Location | "
              "ConvertTo-Json -Compress -Depth 3")
    data = _invoke(run, ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                   8 if number is not None else 12)
    records = json.loads(data.decode("utf-8-sig"))
    if isinstance(records, dict):
        records = [records]
    devices: list[Device] = []
    for record in records or []:
        bus = str(record.get("BusType") or "").lower()
        # Some PowerShell versions serialize BusType as an enum integer.
        # Only positively identified external buses are admitted.
        if bus not in {"usb", "7", "1394", "4", "sd", "12", "mmc", "13"}:
            continue
        if record.get("IsBoot") is not False or record.get("IsSystem") is not False:
            continue
        if record.get("IsOffline") is not False:
            continue
        try:
            number = int(record["Number"])
        except (KeyError, ValueError, TypeError):
            continue
        if number < 0:
            continue
        size = _positive_int(record.get("Size"))
        sector = _positive_int(record.get("LogicalSectorSize"))
        if not size or not sector or size % sector:
            continue
        path = rf"\\.\PhysicalDrive{number}"
        devices.append(Device(f"windows:PhysicalDrive{number}", path,
                              str(record.get("FriendlyName") or "External disk"),
                              size, sector, "usb" if bus in {"usb", "7"} else bus,
                              str(record.get("SerialNumber") or record.get("UniqueId") or ""),
                              str(record.get("Location") or "").strip(), "Get-Disk"))
    return devices


def _parse_usb_disk_records(records: list[dict]) -> list[Device]:
    devices: list[Device] = []
    for record in records or []:
        iface = str(record.get("InterfaceType") or record.get("BusType") or "").upper()
        # Conservative: only USB-attached whole disks.
        if iface not in {"USB", "7"}:
            continue
        try:
            number = int(record.get("Index", record.get("Number")))
        except (KeyError, ValueError, TypeError):
            continue
        if number < 0:
            continue
        size = _positive_int(record.get("Size"))
        sector = _positive_int(
            record.get("BytesPerSector") or record.get("LogicalSectorSize"), 512
        )
        if not size or not sector or size % sector:
            continue
        path = rf"\\.\PhysicalDrive{number}"
        model = str(record.get("Model") or record.get("FriendlyName") or "External USB disk").strip()
        serial = str(record.get("SerialNumber") or record.get("UniqueId") or "").strip()
        devices.append(Device(
            f"windows:PhysicalDrive{number}", path, model, size, sector, "usb", serial, "", "legacy-inventory",
        ))
    return devices


def _windows_devices_from_cim(run: Callable[..., bytes], number: int | None = None) -> list[Device]:
    """Fallback when Get-Disk hangs after USB dock reseat (common on Windows).

    Prefer ``-Filter Index=N`` for mid-job reselect after heavy patient I/O —
    a full Win32_DiskDrive walk can time out while a single-index query still works.
    """
    if number is not None:
        script = (
            f"Get-CimInstance Win32_DiskDrive -Filter \"Index={int(number)}\" | "
            "Select-Object Index,Model,Size,InterfaceType,SerialNumber,BytesPerSector | "
            "ConvertTo-Json -Compress -Depth 3"
        )
        timeout = 8
    else:
        script = (
            "Get-CimInstance Win32_DiskDrive | "
            "Select-Object Index,Model,Size,InterfaceType,SerialNumber,BytesPerSector | "
            "ConvertTo-Json -Compress -Depth 3"
        )
        timeout = 20
    data = _invoke(run, ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], timeout)
    records = json.loads(data.decode("utf-8-sig"))
    if isinstance(records, dict):
        records = [records]
    return _parse_usb_disk_records(list(records or []))


def _windows_devices_from_wmic(run: Callable[..., bytes]) -> list[Device]:
    """Last-resort fallback: WMIC avoids nested PowerShell / Storage-cmdlet hangs."""
    data = _invoke(run,
        ["wmic", "diskdrive", "get",
         "Index,Model,Size,InterfaceType,SerialNumber,BytesPerSector", "/format:csv"], 20)
    text = data.decode("utf-8-sig", errors="replace").strip()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []
    headers = [h.strip() for h in lines[0].split(",")]
    records: list[dict] = []
    for line in lines[1:]:
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < len(headers):
            continue
        row = {headers[i]: cols[i] for i in range(len(headers))}
        records.append(row)
    return _parse_usb_disk_records(records)


def windows_devices(run: Callable[..., bytes] = _run) -> list[Device]:
    # Inventory prefers CIM/WMIC first. Get-Disk frequently hangs after USB dock
    # reseat on Windows and can stall the Storage stack so later finders also
    # time out — leaving the GUI with zero drives even though Win32_DiskDrive
    # still sees the USB patients. CIM/WMIC results are USB-only and remain
    # informational; select_external_device still requires Get-Disk for writes.
    errors: list[str] = []
    last_empty: list[Device] | None = None
    for finder in (_windows_devices_from_cim, _windows_devices_from_wmic,
                   _windows_devices_from_get_disk):
        try:
            found = finder(run)
            if found:
                return found
            last_empty = found
        except (RuntimeError, json.JSONDecodeError, ValueError, TypeError, OSError) as exc:
            errors.append(f"{finder.__name__}: {exc}")
            continue
    if last_empty is not None:
        return last_empty
    raise RuntimeError("Windows external-disk discovery failed (" + "; ".join(errors) + ")")


def list_external_devices(platform: str | None = None,
                          run: Callable[[list[str]], bytes] = _run) -> list[Device]:
    name = platform or sys.platform
    if name.startswith("linux"):
        return linux_devices(run)
    if name == "darwin":
        return macos_devices(run)
    if name == "win32":
        return windows_devices(run)
    raise RuntimeError(f"Unsupported desktop operating system: {name}")


def select_external_device(identifier: str,
                           discover: Callable[[], list[Device]] = list_external_devices) -> Device:
    # Use the same inventory path as ``list`` so GUI identity_hint / confirm-identity
    # fingerprints stay stable. Do NOT prefer a separate Get-Disk-only shortcut here:
    # USB bridges often report a different Size via Get-Disk than Win32_DiskDrive,
    # which previously made every scan/Fix fail with a fingerprint mismatch after
    # CIM-first inventory. Physical writes add assert_windows_external_write_gate().
    #
    # Targeted CIM-by-Index first: after a long patient scan the full inventory
    # walk often times out even though the selected PhysicalDrive is still present.
    if sys.platform == 'win32' and discover is list_external_devices:
        match = re.fullmatch(r'windows:PhysicalDrive(\d+)', identifier)
        if match:
            try:
                direct = _windows_devices_from_cim(_run, number=int(match.group(1)))
                direct = [d for d in direct if d.id == identifier]
                if len(direct) == 1:
                    return direct[0]
            except (RuntimeError, json.JSONDecodeError, ValueError, TypeError, OSError):
                pass
    matches = [device for device in discover() if device.id == identifier]
    if len(matches) != 1:
        raise ValueError("Drive not found in current external-whole-disk inventory. "
                         "Run 'list' again. Internal drives and partitions are excluded.")
    return matches[0]


def verify_windows_patient_still_present(device: Device, *, size_slop_bytes: int = 16 * 1024 * 1024) -> Device:
    """WMI-free mid-job recheck via native PhysicalDrive IOCTL (Admin typically required).

    After heavy USB patient I/O, CIM/Get-Disk often time out even though the same
    ``\\.\PhysicalDriveN`` handle still opens. Keep the inventory Device (and its
    fingerprint) when the native size agrees within ``size_slop_bytes``.
    """
    if sys.platform != 'win32':
        raise RuntimeError('Windows patient handle recheck is Windows-only')
    match = re.fullmatch(r'windows:PhysicalDrive(\d+)', device.id)
    if not match:
        raise RuntimeError('Windows patient handle recheck requires windows:PhysicalDriveN')
    from .windows_native import probe_physicaldrive
    info = probe_physicaldrive(int(match.group(1)))
    size = _positive_int(info.get('size_bytes'))
    if not size:
        raise RuntimeError('Native PhysicalDrive size unavailable during identity recheck')
    if abs(size - device.size_bytes) > size_slop_bytes:
        raise RuntimeError(
            f'Native PhysicalDrive size {size} disagrees with inventory {device.size_bytes}'
        )
    return device


def assert_windows_external_write_gate(device: Device,
                                       run: Callable[..., bytes] = _run) -> None:
    """Fail closed before patient writes if Get-Disk no longer shows this USB whole disk.

    Inventory identity (fingerprint / confirm-identity) stays on the list path.
    Get-Disk is an additional online/external/non-system gate only — USB bridges
    frequently disagree with CIM on Size, so size is not required to match.
    """
    if sys.platform != 'win32':
        return
    match = re.fullmatch(r'windows:PhysicalDrive(\d+)', device.id)
    if not match:
        raise RuntimeError('Windows write gate requires a windows:PhysicalDriveN identifier')
    try:
        found = _windows_devices_from_get_disk(run, number=int(match.group(1)))
    except RuntimeError as exc:
        raise RuntimeError(
            'Selected-disk Get-Disk write gate failed; reconnect the USB dock, '
            'check Windows Disk Management, and retry. No cached device information '
            'can authorize a disk write. ' + str(exc)
        ) from exc
    found = [d for d in found if d.id == device.id]
    if len(found) != 1:
        raise RuntimeError(
            'The selected disk is no longer a verified external, online, non-system disk'
        )
    gated = found[0]
    # Prefer matching serials when both sides report one; blank USB-bridge
    # serials are common and must not block an otherwise verified PhysicalDrive.
    left = device.serial.strip()
    right = gated.serial.strip()
    if left and right and left.casefold() != right.casefold():
        raise RuntimeError('Get-Disk serial disagrees with inventory; refusing raw write')
