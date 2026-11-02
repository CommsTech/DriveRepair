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

    def public(self) -> dict:
        """Do not include full hardware serial numbers in routine output."""
        return {
            "id": self.id, "model": self.model, "size_bytes": self.size_bytes,
            "sector_size": self.sector_size, "bus": self.bus,
            "serial_suffix": ("***" + self.serial[-4:]) if self.serial else "unavailable",
            "location": self.location or "not reported",
            "discovery": self.provenance,
            "identity_hint": self.fingerprint[:12],
        }


def _run(command: list[str], timeout: float = 25) -> bytes:
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=True, timeout=timeout)
        return result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Device discovery failed ({command[0]}): {exc}") from exc


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


def _windows_devices_from_cim(run: Callable[..., bytes]) -> list[Device]:
    """Fallback when Get-Disk hangs after USB dock reseat (common on Windows)."""
    script = (
        "Get-CimInstance Win32_DiskDrive | "
        "Select-Object Index,Model,Size,InterfaceType,SerialNumber,BytesPerSector | "
        "ConvertTo-Json -Compress -Depth 3"
    )
    data = _invoke(run, ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], 20)
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
    # Prefer authoritative Get-Disk: it identifies boot/system disks.
    # Legacy enumeration remains informational and MUST NOT authorize patient writes.
    errors: list[str] = []
    last_empty: list[Device] | None = None
    for finder in (_windows_devices_from_get_disk, _windows_devices_from_cim,
                   _windows_devices_from_wmic):
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
    # A failing USB disk can stall Get-Disk *all* for 12 s, CIM for 20 s,
    # and WMIC for 20 s. Ask for the selected disk only first. This still
    # checks IsBoot/IsSystem/IsOffline and requires model/serial/capacity.
    # Never use a cached inventory or CIM-only fallback as write authority.
    if sys.platform == 'win32' and discover is list_external_devices:
        match = re.fullmatch(r'windows:PhysicalDrive(\d+)', identifier)
        if match:
            try:
                direct = _windows_devices_from_get_disk(_run, number=int(match.group(1)))
                direct = [d for d in direct if d.id == identifier]
                if len(direct) == 1:
                    return direct[0]
                raise RuntimeError('The selected disk is no longer a verified external, online, non-system disk')
            except RuntimeError as exc:
                raise RuntimeError('Selected-disk identity query failed; reconnect the USB dock, '
                                   'check Windows Disk Management, and retry. No cached device '
                                   'information can authorize a disk write. ' + str(exc)) from exc
    matches = [device for device in discover() if device.id == identifier]
    if len(matches) != 1:
        raise ValueError("Drive not found in current external-whole-disk inventory. "
                         "Run 'list' again. Internal drives and partitions are excluded.")
    return matches[0]
