"""Optional privacy-minimal historical anomaly hints, never a repair authorization.

Stores only byte offsets / lengths / observed latency and a keyed fingerprint.
No sector contents, file names, raw disk serials, backups or permissions to write.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

MAX_FILE_BYTES = 192 * 1024
MAX_HINTS = 256


def history_directory() -> Path:
    override = os.environ.get('DRIVEREPAIR_HISTORY_HOME')
    if override:
        return Path(override)
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        return Path(os.environ['LOCALAPPDATA']) / 'DriveRepair' / 'anomalies'
    return Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state') / 'driverepair' / 'anomalies'


def _identity(fingerprint: str, size: int, sector: int):
    if len(fingerprint) < 16 or not isinstance(size, int) or size <= 0 or sector <= 0:
        raise ValueError('Weak or invalid device identity')
    key = hashlib.sha256(f'{fingerprint}|{size}|{sector}'.encode()).hexdigest()
    return key


def _target(fingerprint: str, size: int, sector: int, folder: Path | None):
    key = _identity(fingerprint, size, sector)
    return (folder if folder is not None else history_directory()) / f'{key}.json'


def load_hints(fingerprint: str, size: int, sector: int, *, folder: Path | None = None) -> list[dict]:
    path = _target(fingerprint, size, sector, folder)
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return []
        data = json.loads(path.read_text(encoding='utf8'))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict) or data.get('schema') != 1 or data.get('key') != path.stem:
        return []
    return _validate(data.get('hints'), size, sector)


def _validate(raw, size: int, sector: int) -> list[dict]:
    found = {}
    if not isinstance(raw, list):
        return []
    for item in raw[:MAX_HINTS * 5]:
        if not isinstance(item, dict):
            continue
        off, length = item.get('offset'), item.get('length')
        if (type(off) is not int or type(length) is not int or off < 0 or
                length <= 0 or off + length > size or off % sector or length % sector):
            continue
        found[(off, length)] = {'offset': off, 'length': length,
                                'kind': str(item.get('kind', 'suspect'))[:32]}
        if len(found) >= MAX_HINTS:
            break
    return list(found.values())


def save_hints(fingerprint: str, size: int, sector: int, scan: dict,
               *, folder: Path | None = None) -> dict:
    """Explicitly opted-in. Never save to the source device.

    Requires a local profile/state directory and immutable device fingerprint.
    """
    path = _target(fingerprint, size, sector, folder)
    previous = load_hints(fingerprint, size, sector, folder=folder)
    fresh = []
    for source, name in ((scan.get('read_error_ranges'), 'io_error'),
                         (scan.get('slow_regions'), 'slow'),
                         (scan.get('skipped_untested_ranges'), 'untested')):
        for entry in (source or [])[:MAX_HINTS]:
            if not isinstance(entry, dict):
                continue
            fresh.append({'offset': entry.get('offset'),
                          'length': entry.get('length', min(size, 1024*1024)),
                          'kind': name})
    # Latest findings first so the bounded map retains new anomalies.
    hints = _validate(fresh + previous, size, sector)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = json.dumps({'schema': 1, 'key': path.stem, 'hints': hints}, separators=(',', ':'))
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf8') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
    return {'saved_hints': len(hints), 'location': 'local user application state', 'contains_sector_data': False}
