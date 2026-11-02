"""Read-only host storage facts; no passthrough writes or firmware changes.

These are hints to scan planning, NOT a substitute for device identity or a
physical-write authorization. Unknown values are not guessed.
"""
from __future__ import annotations
import plistlib
from pathlib import Path
import re
import subprocess
import sys


def linux_properties(name: str, *, sys_root: Path = Path('/sys/class/block')) -> dict:
    if not re.fullmatch(r'[a-zA-Z0-9._+-]+', name) or name in {'.','..'}:
        raise ValueError('Invalid block device name')
    node=sys_root/name
    queue=node/'queue'
    if not queue.is_dir():
        raise FileNotFoundError('Linux block queue not available')
    fields={'rotational':'rotational', 'physical_sector_bytes':'physical_block_size',
            'logical_sector_bytes':'logical_block_size',
            'optimal_io_bytes':'optimal_io_size',
            'max_request_kib':'max_sectors_kb',
            'discard_max_bytes':'discard_max_bytes',
            'zoned':'zoned'}
    result={'source':'Linux sysfs block queue','write_authorized':False}
    for out, filename in fields.items():
        try: value=(queue/filename).read_text(encoding='ascii').strip()
        except (FileNotFoundError,OSError):continue
        if out=='rotational':result['rotational']=value=='1' if value in {'0','1'} else None
        elif out=='zoned':result['zoned']=value
        elif value.isdecimal():result[out]=int(value)
    result['notes']='Queue geometry/capabilities may describe a USB bridge. No SMR/CMR inference from rotational flag.'
    return result


def macos_properties(name: str, *, run=subprocess.run) -> dict:
    if not re.fullmatch(r'disk\d+',name):
        raise ValueError('Invalid macOS disk name')
    command=['diskutil','info','-plist',name]
    proc=run(command,capture_output=True,timeout=8,check=True)
    raw=plistlib.loads(proc.stdout)
    if raw.get('WholeDisk') is not True or raw.get('DeviceIdentifier')!=name:
        raise ValueError('Not a current whole disk')
    return {'source':'macOS diskutil', 'write_authorized':False,
            'reported_solid_state':raw.get('SolidState') if isinstance(raw.get('SolidState'),bool) else None,
            'protocol':raw.get('Protocol'), 'logical_sector_bytes':raw.get('DeviceBlockSize'),
            'size_bytes':raw.get('TotalSize'),'smart_status':raw.get('SMARTStatus'),
            'notes':'macOS media properties are advisory and may omit USB SMART/firmware or recording format.'}


def inspect_readonly(device_id: str, *, platform: str | None = None) -> dict:
    platform=platform or sys.platform
    if platform.startswith('linux'):
        match=re.fullmatch(r'linux:/dev/([a-zA-Z0-9._+-]+)',device_id)
        if not match:raise ValueError('Select a Linux whole disk ID')
        return linux_properties(match.group(1))
    if platform=='darwin':
        match=re.fullmatch(r'macos:(disk\d+)',device_id)
        if not match:raise ValueError('Select a macOS whole disk ID')
        return macos_properties(match.group(1))
    if platform=='win32':
        match=re.fullmatch(r'windows:PhysicalDrive(\d+)',device_id)
        if not match:raise ValueError('Select a Windows physical drive ID')
        from .windows_native import probe_physicaldrive
        return probe_physicaldrive(int(match.group(1)))
    raise RuntimeError('Unsupported host platform')
