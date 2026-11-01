"""Conservative scheduled health monitoring; NEVER auto-rewrites sectors.

Health can worsen despite a nominal SMART 'passed' result. Hardware counters
are vendor-specific; trends and unknown conditions are reported separately.
"""
from __future__ import annotations

import json
import os
import stat
import tempfile
from datetime import datetime, timezone


def _numbers(snapshot: dict) -> dict[str, int]:
    health = snapshot.get('health') or {}
    counters = {}
    nvme = health.get('nvme') or {}
    for name in ('media_errors', 'num_err_log_entries', 'critical_warning'):
        value = nvme.get(name)
        if type(value) is int and value >= 0:
            counters[f'nvme.{name}'] = value
    for attribute in health.get('ata_selected_raw_attributes') or []:
        if attribute.get('id') not in {5, 187, 197, 198}:
            continue
        value = attribute.get('raw_value')
        if type(value) is int and value >= 0:
            counters[f'ata.{attribute["id"]}'] = value
    return counters


def evaluate_snapshot(previous: dict | None, current: dict) -> dict:
    """Compare health counters without claiming failures are predictable."""
    if previous and previous.get('fingerprint') != current.get('fingerprint'):
        raise ValueError('Monitor state refers to a different drive; refuse comparison')
    if previous and previous.get('size_bytes') != current.get('size_bytes'):
        raise ValueError('Device capacity changed; monitor state cannot be reused')
    warnings = []
    health = current.get('health') or {}
    if health.get('status') == 'failure_reported':
        warnings.append('SMART reports drive failure or critical concern')
    elif health.get('status') not in {'smart_passed_limited'}:
        warnings.append('SMART health unknown or not available')
    scan = current.get('triage')
    if scan:
        if scan.get('read_error_chunks', 0) > 0 or scan.get('status', '').startswith('aborted'):
            warnings.append('Read errors or access interruption during sampled scan')
        if scan.get('slow_regions'):
            warnings.append('Unusually slow sampled regions; repeat under controlled conditions')
    old = _numbers(previous) if previous else {}
    new = _numbers(current)
    for key, value in new.items():
        if key in old and value > old[key]:
            warnings.append(f'{key} increased ({old[key]} -> {value}); investigate/backup')
    if not previous:
        disposition = 'baseline_recorded'
    else:
        disposition = 'attention' if warnings else 'no_new_signal_observed'
    return {'status': disposition, 'warnings': warnings,
            'notes': 'Not a health certificate. Read-only monitoring cannot predict all failures, '
                     'and NEVER starts repair, writes, self-tests, TRIM, or firmware operations.'}


def load_history(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    if not stat.S_ISREG(os.lstat(path).st_mode):
        raise ValueError('History must be a regular file; symlinks not permitted')
    with open(path, encoding='utf-8') as f:
        state = json.load(f)
    if state.get('schema') != 1 or not isinstance(state.get('history'), list):
        raise ValueError('Unrecognized monitor history')
    if len(state['history']) > 128:
        raise ValueError('Monitor history exceeds safe bound')
    return state['history']


def save_history(path: str, history: list[dict]) -> None:
    """Atomic, owner-only sidecar file, never on the patient drive."""
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        raise ValueError('Monitor state parent directory must exist')
    # Do not accept a symlink state or redirect writes through one.
    if os.path.lexists(path) and not stat.S_ISREG(os.lstat(path).st_mode):
        raise ValueError('Monitor destination is not a regular file')
    fd, temp = tempfile.mkstemp(prefix='.driverepair-monitor-', dir=parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump({'schema': 1, 'history': history[-30:]}, out, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
        if os.name == 'posix':
            dirfd = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def record_monitor_sample(path: str, *, fingerprint: str, size_bytes: int,
                          health: dict, triage: dict | None = None) -> dict:
    history = load_history(path)
    current = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
               'fingerprint': fingerprint, 'size_bytes': size_bytes,
               'health': health, 'triage': triage}
    report = evaluate_snapshot(history[-1] if history else None, current)
    save_history(path, history + [current])
    return {'operation': 'scheduled_monitor', **report, 'history_size': min(len(history)+1, 30),
            'device_identity_hint': fingerprint[:12],
            'sample_time_utc': current['timestamp_utc']}
