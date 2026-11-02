"""Advisory firmware and drive-aware Windows volume optimization.

No firmware downloads/flashing, custom defragmentation, TRIM or arbitrary drive
writes. The OS optimizer is used only with a validated volume mapping and
explicit opt-in, and only when independent health evidence is acceptable.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Callable

from .devices import Device

SEAGATE_SUPPORT = 'https://www.seagate.com/support/downloads/'


def firmware_inventory(device: Device, *, run: Callable = subprocess.run) -> dict:
    """Read-only inventory; do not equate a detected revision with being current."""
    result = {
        'device': device.public(), 'installed_revision': None,
        'update_available': 'NOT_CHECKED', 'firmware_update_performed': False,
        'manufacturer_lookup': SEAGATE_SUPPORT if 'seagate' in device.model.lower() or
        device.model.upper().startswith(('ST', 'ZA', 'ZP')) else None,
        'notes': ('Firmware availability cannot be inferred from a version string. '
                  'Check the exact model, serial, OEM status and bridge compatibility '
                  'with the manufacturer; no firmware updates are executed.'),
    }
    # Windows storage hardware inventory supplies a revision on some devices.
    if sys.platform == 'win32' and re.fullmatch(r'windows:PhysicalDrive\d+', device.id):
        num = int(device.id.split('PhysicalDrive')[-1])
        script = (f'$d = Get-Disk -Number {num} -ErrorAction Stop; '
                  "$p = @(Get-PhysicalDisk | Where-Object { $_.UniqueId -eq $d.UniqueId }); "
                  "if ($p.Count -ne 1) { throw 'Unique firmware mapping unavailable' }; "
                  '[pscustomobject]@{ Revision=[string]$p[0].FirmwareVersion; '
                  'Model=[string]$p[0].FriendlyName } | ConvertTo-Json -Compress')
        try:
            proc = run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                       capture_output=True, timeout=20, check=False)
            if proc.returncode == 0:
                raw = json.loads(proc.stdout.decode('utf-8-sig'))
                if isinstance(raw, dict) and raw.get('Revision'):
                    result['installed_revision'] = str(raw['Revision'])[:120]
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, UnicodeError, AttributeError):
            pass
    # Cross-platform SMART output is optional and informational; some USB docks
    # return bridge firmware instead of the drive's firmware revision.
    if not result['installed_revision']:
        try:
            proc = run(['smartctl', '--json', '--info', device.path],
                       capture_output=True, timeout=20, check=False)
            if proc.returncode & 0x07 == 0:
                raw = json.loads(proc.stdout.decode('utf-8-sig'))
                revision = (raw.get('firmware_version') or raw.get('nvme_firmware_version'))
                if revision:
                    result['installed_revision'] = str(revision)[:120]
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, UnicodeError, AttributeError):
            pass
    return result


def volume_optimization_plan(*, disk: Device, letter: str, facts: dict,
                             smart_state: str = 'unknown') -> dict:
    """Build a conservative plan for one explicitly selected Windows volume."""
    if not re.fullmatch(r'[A-Za-z]', letter):
        raise ValueError('Use a single Windows drive letter, e.g. E')
    if not disk.id.startswith('windows:PhysicalDrive'):
        raise ValueError('Windows disk identity required')
    number = int(disk.id.split('PhysicalDrive')[-1])
    if int(facts.get('DiskNumber', -1)) != number or str(facts.get('DriveLetter', '')).upper() != letter.upper():
        raise ValueError('Volume is not on the selected disk; operation blocked')
    if facts.get('IsBoot') is not False or facts.get('IsSystem') is not False:
        raise ValueError('Refusing system/boot volume optimization')
    media = str(facts.get('MediaType') or 'Unknown').lower()
    filesystem = str(facts.get('FileSystem') or '').upper()
    status = str(facts.get('HealthStatus') or 'Unknown').lower()
    if media in {'hdd', 'hard disk drive'} and filesystem in {'NTFS', 'REFS'}:
        operation = 'defrag'
    elif media in {'ssd', 'solid state drive'} and filesystem in {'NTFS', 'REFS'}:
        operation = 'retrim'
    else:
        operation = 'analyze'
    eligible = (operation != 'analyze' and status == 'healthy' and smart_state == 'smart_passed_limited')
    return {
        'device': disk.public(), 'drive_letter': letter.upper(), 'filesystem': filesystem,
        'media_type': media, 'os_health': status, 'smart_health': smart_state,
        'recommendation': operation, 'eligible_to_execute': eligible,
        'performed': False,
        'notes': ('OS-native optimization only; does not fix bad sectors or reconstruct files. '
                  'No optimization is authorized when SMART evidence is unknown or the drive is deteriorating. '
                  'TRIM can make deleted-data recovery harder. Save important data first.'),
    }


def windows_volume_facts(disk: Device, letter: str, *, run: Callable = subprocess.run) -> dict:
    if sys.platform != 'win32':
        raise RuntimeError('Native volume optimization is Windows-only')
    if not re.fullmatch(r'[A-Za-z]', letter):
        raise ValueError('Invalid Windows drive letter')
    if not re.fullmatch(r'windows:PhysicalDrive\d+', disk.id):
        raise ValueError('A selected Windows physical disk is required')
    num = int(disk.id.split('PhysicalDrive')[-1])
    script = (f'$d = Get-Disk -Number {num} -ErrorAction Stop; '
              f'$p = @(Get-Partition -DiskNumber {num} | Where-Object {{ $_.DriveLetter -eq "{letter.upper()}" }}); '
              "if ($p.Count -ne 1) { throw 'Volume not uniquely mapped' }; "
              '$v = $p[0] | Get-Volume -ErrorAction Stop; '
              '$pd = @(Get-PhysicalDisk | Where-Object { $_.UniqueId -eq $d.UniqueId }); '
              '[pscustomobject]@{ DiskNumber=[int]$d.Number; '
              f'DriveLetter="{letter.upper()}"; IsBoot=[bool]$d.IsBoot; IsSystem=[bool]$d.IsSystem; '
              'FileSystem=[string]$v.FileSystem; HealthStatus=[string]$v.HealthStatus; '
              "MediaType=if ($pd.Count -eq 1) {[string]$pd[0].MediaType} else {'Unknown'} "
              '} | ConvertTo-Json -Compress')
    proc = run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
               capture_output=True, timeout=25, check=False)
    if proc.returncode != 0:
        raise RuntimeError('Cannot establish a unique, trusted volume mapping; no optimization performed')
    raw = json.loads(proc.stdout.decode('utf-8-sig'))
    if not isinstance(raw, dict):
        raise RuntimeError('Unexpected Windows volume metadata')
    return raw


def execute_optimization(plan: dict, *, run: Callable = subprocess.run) -> dict:
    """Explicit opt-in required by CLI caller; refuse unsupported/unknown drives."""
    if sys.platform != 'win32' or not plan.get('eligible_to_execute'):
        raise ValueError('Drive not qualified for write optimization')
    if plan.get('recommendation') not in {'defrag', 'retrim'}:
        raise ValueError('Unsupported optimization action')
    letter = str(plan['drive_letter'])
    if not re.fullmatch('[A-Z]', letter):
        raise ValueError('Invalid mapped volume')
    flag = '-Defrag' if plan['recommendation'] == 'defrag' else '-ReTrim'
    proc = run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                f'Optimize-Volume -DriveLetter {letter} {flag} -ErrorAction Stop'],
               capture_output=True, timeout=7200, check=False)
    return {**plan, 'performed': proc.returncode == 0, 'returncode': proc.returncode,
            'notes': plan['notes'] + ' OS operation executed; verify OS results and health separately.'}
