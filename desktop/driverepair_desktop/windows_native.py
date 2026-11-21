"""Optional READ-ONLY Windows storage properties without Get-Disk/WMIC.

This deliberately does not establish that a disk is not the boot/system disk.
It must never be used as a substitute for the write-authorizing device checks.
Call in an isolated child process, since broken USB hardware can block an IOCTL.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import struct
import sys
from typing import Callable

IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C
# STORAGE_PROPERTY_ID: seek penalty (7), TRIM (8). Both are read-only
# STORAGE_PROPERTY_QUERY requests; a USB bridge may mask or synthesize either.
STORAGE_DEVICE_SEEK_PENALTY_PROPERTY = 7
STORAGE_DEVICE_TRIM_PROPERTY = 8
# STORAGE_BUS_TYPE subset; keep labels aligned with devices.canonicalize_windows_external_bus.
BUS_NAMES = {
    1: 'SCSI', 3: 'ATA', 4: '1394', 7: 'USB', 8: 'RAID', 10: 'SAS', 11: 'SATA',
    12: 'SD', 13: 'MMC', 17: 'NVMe', 18: 'SCM', 19: 'UFS',
}
ERROR_ACCESS_DENIED = 5


def _string(data: bytes, offset: int) -> str | None:
    if not 36 <= offset < len(data):
        return None
    return data[offset:].split(b'\0', 1)[0].decode('ascii', 'replace').strip() or None


def decode_descriptor(data: bytes) -> dict:
    """Parse documented STORAGE_DEVICE_DESCRIPTOR; ignore invalid offsets."""
    if len(data) < 36:
        raise ValueError('Truncated device descriptor')
    version, size = struct.unpack_from('<II', data, 0)
    if size < 36 or size > len(data):
        raise ValueError('Invalid device descriptor length')
    vendor, product, revision, serial, bus = struct.unpack_from('<IIIII', data, 12)
    segment=data[:size]
    return {'vendor': _string(segment, vendor), 'model': _string(segment, product),
            'firmware_revision': _string(segment, revision), 'serial': _string(segment, serial),
            'bus': BUS_NAMES.get(bus, f'bus_type_{bus}'),
            'removable_media': bool(segment[10]),
            'evidence': 'Win32 STORAGE_DEVICE_DESCRIPTOR (may describe USB bridge, not internal media)'}


def decode_alignment(data: bytes) -> dict:
    if len(data) < 28:
        raise ValueError('Truncated alignment descriptor')
    version, size = struct.unpack_from('<II', data)
    if size < 28 or size > len(data):
        raise ValueError('Invalid alignment descriptor')
    logical, physical = struct.unpack_from('<II', data, 16)
    if not 128 <= logical <= 65536 or not 128 <= physical <= 65536:
        raise ValueError('Invalid sector geometry')
    return {'logical_sector_bytes': logical, 'physical_sector_bytes': physical}



def decode_boolean_property(data: bytes, *, property_name: str) -> bool:
    """Parse DEVICE_SEEK_PENALTY_DESCRIPTOR or DEVICE_TRIM_DESCRIPTOR.

    Header: ULONG Version, ULONG Size, BOOLEAN flag (offset 8). Never infer
    a value from a truncated, mismatched or unsupported driver response.
    """
    if len(data) < 9:
        raise ValueError(f'Truncated {property_name} descriptor')
    version, size = struct.unpack_from('<II', data, 0)
    if version < 9 or size < 9 or size > len(data):
        raise ValueError(f'Invalid {property_name} descriptor header')
    if data[8] not in (0, 1):
        raise ValueError(f'Invalid {property_name} descriptor flag')
    return bool(data[8])

def probe_physicaldrive(number: int) -> dict:
    """Read device/adapter capabilities only; never open with write access."""
    if sys.platform != 'win32':
        raise RuntimeError('Windows native storage property query is Windows-only')
    if not 0 <= number <= 255:
        raise ValueError('Invalid physical drive number')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,
                                  ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.DeviceIoControl.argtypes=[wintypes.HANDLE,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,
                                     ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
    kernel.DeviceIoControl.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.CloseHandle.restype=wintypes.BOOL
    path=rf'\\.\PhysicalDrive{number}'
    handle=kernel.CreateFileW(path,0x80000000,3,None,3,0,None)  # GENERIC_READ only
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        def query(code: int, payload: bytes = b'', limit: int = 1024) -> bytes:
            argument=ctypes.create_string_buffer(payload) if payload else None
            output=ctypes.create_string_buffer(limit)
            count=wintypes.DWORD(0)
            ok=kernel.DeviceIoControl(handle,code,argument,len(payload) if payload else 0,
                                       output,limit,ctypes.byref(count),None)
            if not ok:
                raise ctypes.WinError(ctypes.get_last_error())
            return output.raw[:count.value]
        info=decode_descriptor(query(IOCTL_STORAGE_QUERY_PROPERTY,struct.pack('<II',0,0)))
        try:
            info.update(decode_alignment(query(IOCTL_STORAGE_QUERY_PROPERTY,struct.pack('<II',6,0))))
        except (OSError, ValueError):
            info['geometry_note']='Driver did not expose storage alignment property'
        # Both flags are hints from the Windows storage stack, not ATA IDENTIFY.
        # On some USB adapters these queries fail, or describe the bridge.
        for field, property_id in (
            ('incurs_seek_penalty', STORAGE_DEVICE_SEEK_PENALTY_PROPERTY),
            ('trim_enabled', STORAGE_DEVICE_TRIM_PROPERTY),
        ):
            try:
                raw = query(IOCTL_STORAGE_QUERY_PROPERTY,
                            struct.pack('<II', property_id, 0), limit=32)
                info[field] = decode_boolean_property(raw, property_name=field)
            except (OSError, ValueError):
                info[field] = None
        length=query(IOCTL_DISK_GET_LENGTH_INFO,limit=8)
        if len(length)!=8:
            raise ValueError('Invalid disk length response')
        info['size_bytes']=struct.unpack_from('<Q',length)[0]
        info['number']=number
        serial=info.pop('serial',None)
        info['serial_suffix']='***'+serial[-4:] if serial else None
        info['write_authorized']=False
        info['notes']='Read-only driver metadata. Seek penalty and TRIM can be USB-bridge claims; cannot alone prove media health, exclude system disks, or authorize raw writes.'
        return info
    finally:
        kernel.CloseHandle(handle)


def windows_is_elevated() -> bool | None:
    """Return the current Windows administrator-token state, when available.

    This is an operator hint, not a write authorization. Some storage policies
    and filter drivers deny raw access even to an administrator, so callers
    must still test the selected PhysicalDrive handle.
    """
    if sys.platform != 'win32':
        return None
    try:
        shell32 = ctypes.WinDLL('shell32')
        shell32.IsUserAnAdmin.argtypes = []
        shell32.IsUserAnAdmin.restype = ctypes.c_int
        return bool(shell32.IsUserAnAdmin())
    except (AttributeError, OSError, TypeError):
        return None


def _windows_error_code(error: BaseException) -> int | None:
    value = getattr(error, 'winerror', None)
    if type(value) is int:
        return value
    value = getattr(error, 'errno', None)
    return value if type(value) is int else None


def windows_access_failure(number: int, error: BaseException,
                          *, elevated: bool | None = None) -> dict:
    """Create a redacted, actionable report for a failed read-only open."""
    code = _windows_error_code(error)
    if elevated is None:
        elevated = windows_is_elevated()
    if code == ERROR_ACCESS_DENIED:
        return {
            'status': 'raw_access_denied',
            'raw_read_access': 'denied',
            'error_code': ERROR_ACCESS_DENIED,
            'error': 'WinError 5 (ERROR_ACCESS_DENIED)',
            'administrator_token': elevated,
            'elevation_required': True,
            'writes_performed': False,
            'next_steps': [
                'Run DriveRepair from an elevated Administrator session.',
                'Close applications using the volume and check security/filter-driver policy.',
                'If access remains denied, use a trusted read-only recovery environment or another adapter.',
            ],
            'notes': ('Raw access is a prerequisite for a physical-disk scan or repair. '
                      'No scan or patient write was attempted.'),
        }
    return {
        'status': 'raw_access_failed',
        'raw_read_access': 'unknown',
        'error_code': code,
        'error': f'{type(error).__name__}: {str(error)[:240]}',
        'administrator_token': elevated,
        'elevation_required': elevated is False,
        'writes_performed': False,
        'next_steps': [
            'Retry the read-only preflight after reconnecting the selected disk.',
            'Do not bypass the Windows storage or identity checks.',
        ],
        'notes': 'Raw access could not be established; no scan or patient write was attempted.',
    }


def windows_access_preflight(device, *, probe: Callable[[int], dict] | None = None) -> dict:
    """Probe one selected PhysicalDrive with read-only access only.

    A successful descriptor query does not authorize writes; it only proves
    that the current process can reach the selected raw handle at this moment.
    """
    if sys.platform != 'win32':
        raise RuntimeError('Windows raw-access preflight is Windows-only')
    import re
    from .devices import Device
    if not isinstance(device, Device):
        raise TypeError('Windows access preflight requires a selected Device')
    match = re.fullmatch(r'windows:PhysicalDrive(\d+)', device.id)
    expected = rf'\\.\PhysicalDrive{match.group(1)}' if match else ''
    if not match or device.path.casefold() != expected.casefold():
        raise ValueError('Selected Windows device identity/path mismatch')
    number = int(match.group(1))
    elevated = windows_is_elevated()
    try:
        info = (probe or probe_physicaldrive)(number)
    except (OSError, ValueError, TypeError) as exc:
        return {
            'operation': 'windows_access_preflight',
            'device': device.public(),
            **windows_access_failure(number, exc, elevated=elevated),
        }
    return {
        'operation': 'windows_access_preflight',
        'device': device.public(),
        'status': 'read_only_access_available',
        'raw_read_access': 'available',
        'administrator_token': elevated,
        'elevation_required': elevated is not True,
        'writes_performed': False,
        'descriptor': info,
        'notes': ('Read-only PhysicalDrive access succeeded. This does not grant write authority; '
                  'physical writes still require the independent Windows external-disk gate, '
                  'exclusive volume locks, identity confirmation, journal and acknowledgements.'),
    }
