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

IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C
# STORAGE_BUS_TYPE subset; keep labels aligned with devices.canonicalize_windows_external_bus.
BUS_NAMES = {
    1: 'SCSI', 3: 'ATA', 4: '1394', 7: 'USB', 8: 'RAID', 10: 'SAS', 11: 'SATA',
    12: 'SD', 13: 'MMC', 17: 'NVMe', 18: 'SCM', 19: 'UFS',
}


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
        length=query(IOCTL_DISK_GET_LENGTH_INFO,limit=8)
        if len(length)!=8:
            raise ValueError('Invalid disk length response')
        info['size_bytes']=struct.unpack_from('<Q',length)[0]
        info['number']=number
        serial=info.pop('serial',None)
        info['serial_suffix']='***'+serial[-4:] if serial else None
        info['write_authorized']=False
        info['notes']='Read-only metadata. Does NOT prove IsBoot/IsSystem, identify platter type, or authorize raw writes.'
        return info
    finally:
        kernel.CloseHandle(handle)
