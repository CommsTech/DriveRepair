"""Privacy-minimal local UI preferences.

Never persist device identifiers, risk acknowledgments, patient paths or secrets.
A preference is NOT authorization to modify a drive.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULTS = {
    'schema': 1,
    'repair_storage': 'disk',   # durable journal is the safest default
    'repair_policy': 'balanced',
    'dashboard': False,
}


def preferences_path(*, home: Path | None = None, platform: str | None = None,
                     environ: dict | None = None) -> Path:
    env = environ if environ is not None else os.environ
    system = platform or sys.platform
    if home is not None:
        return Path(home) / '.driverepair' / 'preferences.json'
    if system == 'win32':
        base = env.get('LOCALAPPDATA')
        if base:
            return Path(base) / 'DriveRepair' / 'preferences.json'
    if system == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'DriveRepair' / 'preferences.json'
    return Path(env.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'driverepair' / 'preferences.json'


def valid_preferences(candidate: object) -> dict:
    out = dict(DEFAULTS)
    if not isinstance(candidate, dict) or candidate.get('schema') != 1:
        return out
    if candidate.get('repair_storage') in ('disk', 'memory'):
        out['repair_storage'] = candidate['repair_storage']
    if candidate.get('repair_policy') in ('balanced', 'preserve'):
        out['repair_policy'] = candidate['repair_policy']
    if type(candidate.get('dashboard')) is bool:
        out['dashboard'] = candidate['dashboard']
    return out


def load_preferences(path: Path | None = None) -> dict:
    target = path or preferences_path()
    try:
        if target.stat().st_size > 4096:
            return dict(DEFAULTS)
        return valid_preferences(json.loads(target.read_text(encoding='utf-8')))
    except (OSError, ValueError, UnicodeError):
        return dict(DEFAULTS)


def save_preferences(candidate: dict, path: Path | None = None) -> None:
    """Atomic, best-effort private preference save; no persisted authorization."""
    target = path or preferences_path()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = json.dumps(valid_preferences({**candidate, 'schema': 1}), indent=2) + '\n'
    temp = target.with_name(target.name + '.tmp.' + str(os.getpid()))
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, target)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
