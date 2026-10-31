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

    @property
    def fingerprint(self) -> str:
        data = (self.id, self.path, self.model, str(self.size_bytes),
                str(self.sector_size), self.bus, self.serial)
        return hashlib.sha256("\0".join(data).encode("utf-8")).hexdigest()

    def public(self) -> dict:
        """Do not include full hardware serial numbers in routine output."""
        return {
            "id": self.id, "model": self.model, "size_bytes": self.size_bytes,
            "sector_size": self.sector_size, "bus": self.bus,
            "serial_suffix": ("***" + self.serial[-4:]) if self.serial else "unavailable",
        }


def _run(command: list[str]) -> bytes:
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=True, timeout=25)
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


def linux_devices(run: Callable[[list[str]], bytes] = _run) -> list[Device]:
    command = ["lsblk", "--json", "--bytes", "--nodeps", "--output",
               "PATH,TYPE,TRAN,HOTPLUG,RM,SIZE,LOG-SEC,MODEL,SERIAL"]
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
        if not external or not re.fullmatch(r"/dev/[a-zA-Z0-9._+-]+", path):
            continue
        if not size or not sector or size % sector:
            continue
        devices.append(Device("linux:" + path, path,
                              str(record.get("model") or "Unknown disk").strip(),
                              size, sector, bus, str(record.get("serial") or "").strip()))
    return devices


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
                              str(info.get("DiskUUID") or info.get("MediaUUID") or "")))
    return devices


def windows_devices(run: Callable[[list[str]], bytes] = _run) -> list[Device]:
    # A fixed script, not user input. No mutating PowerShell cmdlets.
    script = ("Get-Disk | Select-Object Number,FriendlyName,SerialNumber,UniqueId,"
              "Size,LogicalSectorSize,BusType,IsBoot,IsSystem,IsOffline | "
              "ConvertTo-Json -Compress -Depth 3")
    data = run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
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
                              size, sector, bus,
                              str(record.get("SerialNumber") or record.get("UniqueId") or "")))
    return devices


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
    matches = [device for device in discover() if device.id == identifier]
    if len(matches) != 1:
        raise ValueError("Drive not found in current external-whole-disk inventory. "
                         "Run 'list' again. Internal drives and partitions are excluded.")
    return matches[0]
