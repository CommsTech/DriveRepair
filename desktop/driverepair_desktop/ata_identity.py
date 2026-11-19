"""Bounded, READ-ONLY ATA IDENTIFY fallback for compatible Windows SAT USB bridges.

Unlike seek/trim heuristics, a valid ATA IDENTIFY block reports the ATA media's
own model, serial, capacity and rotation-rate field. The command is issued in an
isolated child with a bounded parent deadline by ``windows_ata_snapshot``.

No SMART health information is fabricated; ATA IDENTIFY is NOT a write permit.
The guarded engine independently enforces confirmation, Windows disk admission,
exclusive locks, separate durable rollback journal, and explicit unknown-health
consent. Some USB bridges will reject this harmless read-only command.
"""
from __future__ import annotations

import ctypes
import json
import re
import struct
import subprocess
import sys

from .devices import Device
from .media_profiles import identify_profile

SOURCE = 'windows_ata_identify_hdd'
IOCTL_SCSI_PASS_THROUGH = 0x4D004


class _SCSI_PASS_THROUGH(ctypes.Structure):
    _fields_ = [
        ('Length', ctypes.c_uint16), ('ScsiStatus', ctypes.c_uint8),
        ('PathId', ctypes.c_uint8), ('TargetId', ctypes.c_uint8),
        ('Lun', ctypes.c_uint8), ('CdbLength', ctypes.c_uint8),
        ('SenseInfoLength', ctypes.c_uint8), ('DataIn', ctypes.c_uint8),
        ('DataTransferLength', ctypes.c_uint32), ('TimeOutValue', ctypes.c_uint32),
        ('DataBufferOffset', ctypes.c_size_t), ('SenseInfoOffset', ctypes.c_uint32),
        ('Cdb', ctypes.c_uint8 * 16),
    ]


def _ata_text(data: bytes, start_word: int, count: int) -> str:
    # ATA IDENTIFY strings store each ASCII pair in reversed byte order.
    payload = bytearray()
    for pos in range(start_word * 2, (start_word + count) * 2, 2):
        payload.extend((data[pos + 1], data[pos]))
    return payload.decode('ascii', 'replace').strip(' \x00')


def parse_ata_identify(data: bytes) -> dict:
    """Only accept an apparently complete IDENTIFY DEVICE reply with sane fields."""
    if len(data) != 512 or not any(data):
        raise ValueError('ATA IDENTIFY response is empty or truncated')
    words = struct.unpack('<256H', data)
    # Bit 15 of word 0 identifies packet devices; never classify optical ATA as HDD.
    if words[0] & 0x8000:
        raise ValueError('ATA packet device is not a physical HDD')
    model = _ata_text(data, 27, 20)
    serial = _ata_text(data, 10, 10)
    if not (8 <= len(model) <= 40 and 4 <= len(serial) <= 20):
        raise ValueError('ATA IDENTIFY model or serial is incomplete')
    if not all(32 <= ord(ch) < 127 for ch in model + serial):
        raise ValueError('ATA IDENTIFY contains invalid model/serial characters')
    rpm = words[217]
    if rpm == 1:
        medium = 'ssd'
    elif 360 <= rpm <= 30000:
        medium = 'hdd'
    else:
        medium = 'unknown'
    sectors = (words[100] | (words[101] << 16) | (words[102] << 32) |
               (words[103] << 48))
    if not sectors:
        sectors = words[60] | (words[61] << 16)
    # Logical-sector size from IDENTIFY words 106,117,118 when valid.
    logical = 512
    if words[106] & 0xD000 == 0x5000:
        reported = (words[118] << 16) | words[117]
        if 256 <= reported <= 32768:
            logical = reported * 2
    if not sectors or sectors * logical > (1 << 75):
        raise ValueError('ATA IDENTIFY capacity is invalid')
    return {'model': model, 'serial_suffix': '***' + serial[-4:],
            'size_bytes': sectors * logical, 'logical_sector_bytes': logical,
            'rotation_rate': rpm if medium != 'unknown' else None,
            'reported_medium': medium, 'evidence': 'ATA IDENTIFY DEVICE via SAT16'}


def sat_identify_cdb() -> bytes:
    # ATA PASS-THROUGH(16), PIO Data-In, 1 sector, command 0xEC (IDENTIFY).
    return bytes((0x85, 0x08, 0x0e, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0xec, 0))


def inspect_windows_sat(number: int) -> dict:
    """One read-only SAT command; isolated in a short-lived subprocess by caller."""
    if sys.platform != 'win32':
        raise RuntimeError('Windows SATA/SAT passthrough only')
    if not isinstance(number, int) or not 0 <= number <= 255:
        raise ValueError('Invalid physical disk number')
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                        wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    kernel.DeviceIoControl.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(r'\\.\PhysicalDrive' + str(number), 0x80000000, 3,
                                None, 3, 0, None)  # GENERIC_READ only
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        header = ctypes.sizeof(_SCSI_PASS_THROUGH)
        sense_off = (header + 7) & ~7
        data_off = (sense_off + 32 + 7) & ~7
        length = data_off + 512
        packet = ctypes.create_string_buffer(length)
        cdb = _SCSI_PASS_THROUGH.from_buffer(packet)
        cdb.Length = header
        cdb.CdbLength = 16
        cdb.SenseInfoLength = 32
        cdb.SenseInfoOffset = sense_off
        cdb.DataIn = 1  # SCSI_IOCTL_DATA_IN, never send data to device
        cdb.DataTransferLength = 512
        cdb.TimeOutValue = 5
        cdb.DataBufferOffset = data_off
        for i, byte in enumerate(sat_identify_cdb()):
            cdb.Cdb[i] = byte
        count = wintypes.DWORD(0)
        ok = kernel.DeviceIoControl(handle, IOCTL_SCSI_PASS_THROUGH,
                                    packet, length, packet, length,
                                    ctypes.byref(count), None)
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        if cdb.ScsiStatus != 0 or cdb.DataTransferLength != 512 or count.value < header:
            raise ValueError('USB bridge rejected or truncated the ATA IDENTIFY response')
        result = parse_ata_identify(packet.raw[data_off:data_off + 512])
        result['number'] = number
        return result
    finally:
        kernel.CloseHandle(handle)


def interpret_sat_evidence(device: Device, ata: dict) -> dict | None:
    """Corroboration cannot invent healthy SMART or erase a contradictory result."""
    if device.bus.lower() not in {'usb', 'thunderbolt', 'firewire'}:
        return None
    if ata.get('reported_medium') != 'hdd':
        return None
    profile = identify_profile(model=device.model, bus=device.bus,
                               sector=device.sector_size)
    if profile.kind in {'ssd', 'nvme', 'flash'}:
        return None
    def token(value: str) -> str:
        return re.sub(r'[^A-Z0-9]', '', str(value).upper())
    model = token(device.model)
    actual = token(ata.get('model', ''))
    serial = device.serial.strip()
    suffix = str(ata.get('serial_suffix') or '')
    if not (len(model) >= 8 and len(actual) >= 8 and
            (actual in model or model in actual)):
        return None
    if not (len(serial) >= 4 and suffix.endswith(serial[-4:])):
        return None
    if ata.get('size_bytes') != device.size_bytes:
        return None
    if ata.get('logical_sector_bytes') != device.sector_size:
        return None
    return {'source': SOURCE, 'status': 'unknown', 'reported_medium': 'hdd',
            'native_hdd_corrob': True, 'ata_identify_corrob': True,
            'native_factors': ['ATA IDENTIFY model matches inventory',
                               'ATA IDENTIFY serial suffix matches inventory',
                               'ATA IDENTIFY capacity and logical sector agree',
                               'ATA IDENTIFY reports mechanical rotational speed'],
            'rotation_rate': ata.get('rotation_rate'),
            'smart_status_passed': None, 'temperature_c': None,
            'ata_selected_raw_attributes': [], 'nvme': {}, 'device': device.public(),
            'notes': 'Read-only ATA IDENTIFY through USB SAT; no SMART health evidence. '
                     'Requires independently validated physical disk identity, exclusive '
                     'locks, durable separate journal and explicit UNKNOWN-health consent.'}


def windows_ata_snapshot(device: Device, *, runner=subprocess.run) -> dict | None:
    if sys.platform != 'win32':
        return None
    match = re.fullmatch(r'windows:PhysicalDrive(\d+)', device.id)
    if not match:
        return None
    try:
        command = [sys.executable, '-m', 'driverepair_desktop',
                   'inspect-windows-ata', '--number', match.group(1)]
        done = runner(command, capture_output=True, timeout=8, check=False)
        if done.returncode:
            return None
        report = json.loads(done.stdout.decode('utf-8-sig') if isinstance(done.stdout, bytes)
                            else done.stdout)
        if not isinstance(report, dict) or report.get('number') != int(match.group(1)):
            return None
        return interpret_sat_evidence(device, report)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired, UnicodeError):
        return None
