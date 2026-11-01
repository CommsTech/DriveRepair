"""Read-only drive health snapshot via an optional smartctl installation.

Unknown must remain unknown. SMART PASSED is not a clean bill of health.
Hardware information is summarized with serial numbers omitted.
"""
from __future__ import annotations

import json
import subprocess
from typing import Callable

from .devices import Device


def health_snapshot(device: Device,
                    run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict:
    cmd = ['smartctl', '--json', '--all', device.path]
    try:
        proc = run(cmd, capture_output=True, timeout=30, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError('SMART support requires smartctl (smartmontools), not installed') from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('SMART query timed out; device health unknown') from exc
    try:
        raw = json.loads(proc.stdout.decode('utf-8-sig'))
    except (ValueError, UnicodeError, AttributeError) as exc:
        raise RuntimeError('smartctl did not provide valid JSON; device health unknown') from exc
    if not isinstance(raw, dict):
        raise RuntimeError('Unexpected smartctl JSON structure')
    # CLI command, open/identity and SMART command failures invalidate the snapshot.
    # Other smartctl bits describe actual health concerns and must be retained.
    if proc.returncode & 0x07:
        raise RuntimeError(f'SMART probe failed (status bits {proc.returncode & 0x07}); health unknown')
    passed = (raw.get('smart_status') or {}).get('passed')
    status = ('failure_reported' if proc.returncode & (0x08 | 0x10) or passed is False
              else 'smart_passed_limited' if passed is True
              else 'unknown')
    nvme = raw.get('nvme_smart_health_information_log') or {}
    temp = raw.get('temperature') or {}
    ata = raw.get('ata_smart_attributes') or {}
    attrs = []
    for item in ata.get('table', []):
        if item.get('id') not in {5, 187, 188, 197, 198, 199}:
            continue
        attrs.append({'id': item.get('id'), 'name': item.get('name'),
                      'raw_value': (item.get('raw') or {}).get('value')})
    return {
        'status': status,
        'device': device.public(),
        'smartctl_exit_status': proc.returncode,
        'smart_status_passed': passed if isinstance(passed, bool) else None,
        'temperature_c': temp.get('current'),
        'nvme': {k: nvme.get(k) for k in ('percentage_used', 'media_errors',
                 'num_err_log_entries', 'unsafe_shutdowns', 'critical_warning', 'power_on_hours')
                 if k in nvme},
        'ata_selected_raw_attributes': attrs,
        'notes': 'Read-only SMART health snapshot. Raw ATA counters are manufacturer-specific. '
                 'SMART pass does not rule out media defects or future failure. '
                 'No self-test, erase, remap, refresh, or repair was started.',
    }
