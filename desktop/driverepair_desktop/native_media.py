"""Corroborated native Windows media identification when SMART is unavailable.

Never substitutes for a SMART health test. The native disk query runs in a
bounded child process: an unresponsive USB IOCTL must not wedge the GUI.
Media identity only qualifies a *candidate* for an expressly acknowledged
unknown-health guarded HDD workflow. All preexisting OS write gates remain.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

from .devices import Device
from .media_profiles import identify_profile

NATIVE_SOURCE = 'windows_native_corrob_hdd'


def _model_tokens(model: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', model.upper())


def interpret_native_evidence(device: Device, native: dict) -> dict:
    """Assess independent reported geometry/media flags; never infer health.

    A stable serial match, exact size, OEM model match and both mechanical
    properties are required for the guarded native-HDD candidate path.
    A generic USB/flash bridge or unknown model remains read-only.
    """
    factors = []
    model = _model_tokens(device.model)
    native_model = _model_tokens(str(native.get('model') or ''))
    profile = identify_profile(model=device.model, bus=device.bus,
                               sector=device.sector_size)
    # A few common whole-disk OEM part-number formats. This supports
    # non-SMR HDD families *without* guessing their CMR/SMR recording type.
    # It is never used by itself: the separate driver flags, exact capacity,
    # actual descriptor model, and serial must also agree.
    oem_hdd_pattern = bool(re.search(
        r'(?:ST\d{3,5}[A-Z]{1,3}\d{2,4}|WD\d{2,4}[A-Z0-9]{5,9}|'
        r'MQ\d{2}[A-Z]{2,4}\d{2,4})', model))
    model_is_hdd_candidate = (profile.kind in {'smr', 'cmr', 'hdd_unknown_recording'}
                               or (oem_hdd_pattern and profile.kind == 'unknown'))
    size_matches = (type(native.get('size_bytes')) is int and
                    native['size_bytes'] == device.size_bytes)
    if size_matches:
        factors.append('exact logical drive size')
    suffix = str(native.get('serial_suffix') or '')
    serial_matches = (len(device.serial.strip()) >= 4 and
                      len(suffix) >= 7 and
                      suffix.endswith(device.serial[-4:]))
    if serial_matches:
        factors.append('reported serial suffix matches inventory')
    # Confirm actual model token was returned by the Windows device descriptor,
    # not simply copied from the model database. Never rely on "USB device".
    model_matches = (model_is_hdd_candidate
                     and len(native_model) >= 8 and len(model) >= 8
                     and (native_model in model or model in native_model
                          or any(token in native_model for token in
                                 ('ST1000LM048', 'ST500LM030', 'ST500LM034')
                                 if token in model)))
    if model_matches:
        factors.append('OEM HDD model corroborated by device descriptor')
    seek = native.get('incurs_seek_penalty') is True
    trim_absent = native.get('trim_enabled') is False
    if seek:
        factors.append('Windows driver reports mechanical seek penalty')
    if trim_absent:
        factors.append('Windows driver reports no TRIM support')
    bus_matches = (str(native.get('bus') or '').lower() == device.bus.lower()
                   and device.bus.lower() in {'usb', '1394', 'firewire', 'thunderbolt'})
    # USB is a bus, not proof; comparison defends against mixing two disk handles.
    if bus_matches:
        factors.append('reported transport matches inventory')
    qualified = all((size_matches, serial_matches, model_matches,
                     seek, trim_absent, bus_matches))
    if native.get('trim_enabled') is True or native.get('incurs_seek_penalty') is False:
        medium = 'ssd' if native.get('trim_enabled') is True else 'unknown'
    else:
        medium = 'hdd' if qualified else 'unknown'
    return {
        'source': NATIVE_SOURCE if qualified else 'windows_native_unverified',
        'status': 'unknown', 'reported_medium': medium,
        'native_hdd_corrob': qualified, 'native_factors': factors,
        'native_media_properties': {
            'incurs_seek_penalty': native.get('incurs_seek_penalty'),
            'trim_enabled': native.get('trim_enabled'),
            'bus': native.get('bus'),
        },
        'smartctl_exit_status': None, 'smart_status_passed': None,
        'temperature_c': None, 'ata_selected_raw_attributes': [], 'nvme': {},
        'device': device.public(),
        'notes': ('Windows native storage-property evidence; no SMART counters. '
                  'A USB bridge can misreport media properties. '
                  'Even a corroborated HDD is not declared healthy. '
                  'Physical writes require independent identity/locking/journal '
                  'checks and explicit acceptance of UNKNOWN health.'),
    }


def windows_native_snapshot(device: Device, *, runner=subprocess.run) -> dict | None:
    if sys.platform != 'win32':
        return None
    match = re.fullmatch(r'windows:PhysicalDrive(\d+)', device.id)
    if not match:
        return None
    try:
        proc = runner([sys.executable, '-m', 'driverepair_desktop',
                       'inspect-windows-disk', '--number', match.group(1)],
                      capture_output=True, timeout=9, check=False)
        if proc.returncode:
            return None
        raw = json.loads(proc.stdout.decode('utf-8-sig')
                         if isinstance(proc.stdout, bytes) else proc.stdout)
        if not isinstance(raw, dict):
            return None
        return interpret_native_evidence(device, raw)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError,
            ValueError, TypeError, UnicodeError):
        return None
