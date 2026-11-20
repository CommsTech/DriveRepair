"""Explicitly approved Windows *logical filesystem* repair on an external volume.

This is not SSD wear repair or HDD sector remapping.  Never infer a safe target
from a drive letter alone: independently bind the volume to an inventoried,
non-system external physical disk immediately before chkdsk can modify it.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

from .devices import (Device, assert_windows_external_write_gate,
                      select_external_device)
from .media_refresh import assert_stable_identity

_SUPPORTED = {'NTFS', 'EXFAT', 'FAT', 'FAT32'}


def _letter(value: str) -> str:
    token = str(value).strip().upper().rstrip(':')
    if not re.fullmatch(r'[D-Z]', token):
        raise ValueError('Select a non-system Windows volume letter D through Z')
    return token


def parse_volume_binding(raw: bytes, *, device: Device, letter: str) -> dict:
    """Validate the direct Get-Partition/Get-Disk/Get-Volume relationship.

    No disk/volume/model matching heuristic can substitute for DiskNumber.
    """
    try:
        record = json.loads(raw.decode('utf-8-sig'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError('Windows returned invalid volume binding evidence') from exc
    if not isinstance(record, dict):
        raise RuntimeError('Windows did not return a unique volume binding')
    number_match = re.fullmatch(r'windows:PhysicalDrive(\d+)', device.id)
    if not number_match:
        raise PermissionError('Only a selected Windows physical disk is supported')
    expected = int(number_match.group(1))
    try:
        number = int(record['disk_number'])
        size = int(record['disk_size'])
    except (KeyError, ValueError, TypeError) as exc:
        raise RuntimeError('Windows volume/disk identity evidence incomplete') from exc
    if number != expected:
        raise PermissionError('Volume belongs to a DIFFERENT physical disk')
    if abs(size - device.size_bytes) > 16 * 1024 * 1024:
        raise PermissionError('Selected volume disk capacity changed')
    if record.get('is_boot') is not False or record.get('is_system') is not False or record.get('is_offline') is not False:
        raise PermissionError('System, boot, or offline disk cannot be repaired here')
    if str(record.get('volume_letter', '')).upper() != letter:
        raise PermissionError('Volume drive letter changed while being inspected')
    fs = str(record.get('filesystem', '')).upper()
    if fs not in _SUPPORTED:
        raise PermissionError('Only mounted NTFS, exFAT and FAT volumes support this Windows repair')
    if record.get('volume_health') in ('Unknown', None, ''):
        # A status of unknown is not a repair permit or a reason to pretend healthy.
        pass
    return {'disk_number': number, 'disk_size': size, 'letter': letter,
            'filesystem': fs, 'health': record.get('volume_health') or 'Unknown',
            'status': 'volume_bound_readonly', 'media_identity_hint': device.fingerprint[:12]}


def parse_repairable_volumes(raw: bytes, *, device: Device) -> list[dict]:
    """Read-only, exact PhysicalDrive-to-partition bindings for a repair picker.

    The picker is NOT an authorization. The modifying CLI re-enumerates the
    selected disk and rechecks the exact volume immediately before CHKDSK.
    """
    try:
        records = json.loads(raw.decode('utf-8-sig'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError('Windows did not return usable partition information') from exc
    if not isinstance(records, list):
        raise RuntimeError('Windows did not return a partition list')
    matched: list[dict] = []
    letters: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError('Ambiguous Windows partition information')
        letter = str(record.get('volume_letter') or '').strip().upper()
        if not re.fullmatch(r'[D-Z]', letter):
            continue
        if letter in letters:
            raise RuntimeError('Windows listed the same volume more than once')
        letters.add(letter)
        if str(record.get('filesystem') or '').upper() not in _SUPPORTED:
            continue
        # Every candidate is independently validated, including disk number,
        # disk capacity, OS boot/system flags, and the volume-to-disk binding.
        matched.append(parse_volume_binding(json.dumps(record).encode('utf-8'),
                                            device=device, letter=letter))
    return sorted(matched, key=lambda record: record['letter'])


def inspect_windows_repairable_volumes(device: Device, *, run=None) -> list[dict]:
    """List mounted, eligible filesystem volumes on ONE selected external disk.

    This is a READ-ONLY convenience query. It does not open any raw disk for
    writing, lock volumes, or grant permission for in-place filesystem repair.
    """
    if sys.platform != 'win32':
        raise RuntimeError('Windows volume selection requires Windows')
    number_match = re.fullmatch(r'windows:PhysicalDrive(\d+)', device.id)
    if not number_match:
        raise PermissionError('Select a Windows physical external disk first')
    number = int(number_match.group(1))
    script = (
        "$ErrorActionPreference='Stop';"
        f"$d=Get-Disk -Number {number} -ErrorAction Stop;"
        "if($d.IsBoot -or $d.IsSystem -or $d.IsOffline){throw 'Unsafe disk'};"
        f"$parts=@(Get-Partition -DiskNumber {number} -ErrorAction Stop);"
        "$result=@(foreach($p in $parts){"
        "if([string]$p.DriveLetter -match '^[D-Z]$'){"
        "$v=$p | Get-Volume -ErrorAction SilentlyContinue;"
        "if($null -ne $v){"
        "[pscustomobject]@{disk_number=[int]$p.DiskNumber;disk_size=[long]$d.Size;"
        "is_boot=[bool]$d.IsBoot;is_system=[bool]$d.IsSystem;"
        "is_offline=[bool]$d.IsOffline;volume_letter=[string]$p.DriveLetter;"
        "filesystem=[string]$v.FileSystem;volume_health=[string]$v.HealthStatus}"
        "}}});"
        "ConvertTo-Json -InputObject $result -Compress -Depth 4"
    )
    runner = run if run is not None else subprocess.run
    try:
        response = runner(['powershell.exe', '-NoProfile', '-NonInteractive',
                           '-Command', script], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                          timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('Windows volume discovery timed out; no repair was started') from exc
    if response.returncode != 0:
        raise RuntimeError('Windows could not enumerate partitions on the selected disk; no repair started')
    return parse_repairable_volumes(response.stdout, device=device)


def inspect_windows_volume(device: Device, letter: str, *, run=None) -> dict:
    """Read-only Windows metadata. No volume opened for writes."""
    if sys.platform != 'win32':
        raise RuntimeError('On-device Windows filesystem repair requires Windows')
    letter = _letter(letter)
    assert_windows_external_write_gate(device)
    script = (
        "$ErrorActionPreference='Stop';"
        f"$p=Get-Partition -DriveLetter '{letter}' -ErrorAction Stop;"
        "if(@($p).Count -ne 1){ throw 'Ambiguous volume partition' };"
        "$d=Get-Disk -Number ([int]$p.DiskNumber) -ErrorAction Stop;"
        f"$v=Get-Volume -DriveLetter '{letter}' -ErrorAction Stop;"
        "[pscustomobject]@{disk_number=[int]$d.Number;disk_size=[long]$d.Size;"
        "is_boot=[bool]$d.IsBoot;is_system=[bool]$d.IsSystem;is_offline=[bool]$d.IsOffline;"
        "volume_letter=[string]$v.DriveLetter;filesystem=[string]$v.FileSystem;"
        "volume_health=[string]$v.HealthStatus} | ConvertTo-Json -Compress"
    )
    runner = run if run is not None else subprocess.run
    try:
        response = runner(['powershell.exe', '-NoProfile', '-NonInteractive',
                           '-Command', script], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                          timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('Windows could not inspect the volume within 12 seconds; no writes attempted') from exc
    if response.returncode != 0:
        raise RuntimeError('Windows could not map the volume to the selected disk; no writes attempted')
    return parse_volume_binding(response.stdout, device=device, letter=letter)


def windows_filesystem_maintenance(device_id: str, letter: str, *,
                                   confirm_identity: str = '',
                                   execute: bool = False,
                                   ack_backup: bool = False,
                                   ack_write: bool = False,
                                   runner=None) -> dict:
    """Repair on-device filesystem metadata with CHKDSK /f, never raw media.

    No /r, /b, /x, /spotfix, /forceofflinefix or destructive format. If the
    volume is busy, CHKDSK must not be auto-scheduled for the next reboot.
    """
    if sys.platform != 'win32':
        raise RuntimeError('Windows-only filesystem repair')
    selected = select_external_device(device_id)
    letter = _letter(letter)
    if selected.fingerprint[:12] != confirm_identity:
        raise PermissionError('Selected device fingerprint does not match operator approval')
    bind = inspect_windows_volume(selected, letter)
    if not execute:
        return {**bind, 'mode': 'read_only_plan', 'writes_performed': False,
                'notes': 'Filesystem metadata repair is possible, but may discard damaged file records. '
                         'This does not repair physical flash, HDD mechanics, or unreadable bytes.'}
    from .release_policy import PUBLIC_BETA_IMAGE_ONLY
    if PUBLIC_BETA_IMAGE_ONLY:
        raise PermissionError('This public beta cannot modify a patient filesystem')
    if not (ack_backup and ack_write):
        raise PermissionError('Physical source backup and destructive filesystem repair approvals are mandatory')
    # A fresh native inventory and a fresh independent write gate before disk I/O.
    current = select_external_device(device_id)
    assert_stable_identity(selected, current)
    assert_windows_external_write_gate(current)
    check = inspect_windows_volume(current, letter)
    if check['disk_number'] != bind['disk_number'] or check['filesystem'] != bind['filesystem']:
        raise PermissionError('Volume identity or filesystem changed during preflight')
    do_run = runner if runner is not None else subprocess.run
    try:
        completed = do_run(['chkdsk.exe', f'{letter}:', '/f'],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=1800, check=False)
    except subprocess.TimeoutExpired:
        return {**check, 'status': 'filesystem_repair_timeout_unknown',
                'writes_performed': 'unknown', 'notes': 'Timed out. The volume may be inconsistent; '
                'do not disconnect it while Windows still has pending I/O.'}
    output = completed.stdout.decode('utf-8', 'replace')[-10000:]
    # A successful command exit is not independently verified file integrity.
    status = 'repair_command_completed_unverified' if completed.returncode == 0 else 'repair_incomplete_or_failed'
    return {**check, 'status': status, 'mode': 'in_place_filesystem_repair',
            'exit_code': completed.returncode, 'log': output,
            'writes_performed': 'possible',
            'notes': 'CHKDSK /f repairs filesystem metadata, not physical media. '
                     'Run a separate verification and inspect the recovered files. '
                     'A busy/locked volume must be handled offline, not forced.'}
