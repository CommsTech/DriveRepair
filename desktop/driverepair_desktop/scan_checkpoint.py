"""Private, non-authoritative checkpoints for restarting READ-ONLY full scans.

A checkpoint records positions and observations, not recovered sector data.
It can never authorize a physical-device write. The caller MUST freshly
verify the selected device before loading/resuming an interrupted scan.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import time

SCHEMA = 1


def default_path(source_token: str) -> Path:
    digest = hashlib.sha256(source_token.encode('utf-8')).hexdigest()[:32]
    return Path.home() / '.driverepair' / 'scan-checkpoints' / f'{digest}.json'


def load(path: str | Path, *, source_token: str, size: int, sector: int) -> dict:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing or non-regular scan checkpoint')
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('Scan checkpoint exceeds safety size limit')
    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)
    if (type(data) is not dict or data.get('schema') != SCHEMA or
            data.get('source_token') != source_token or
            data.get('size') != size or data.get('sector') != sector):
        raise ValueError('Checkpoint does not match the freshly identified source')
    state = data.get('state')
    if type(state) is not dict:
        raise ValueError('Invalid checkpoint state')
    offset = state.get('position')
    if (type(offset) is not int or offset < 0 or offset > size or offset % sector):
        raise ValueError('Invalid or unaligned checkpoint position')
    for name in ('checked', 'readable', 'read_count', 'failures'):
        if type(state.get(name)) is not int or state[name] < 0:
            raise ValueError(f'Invalid checkpoint counter: {name}')
    for name in ('deferred', 'slow', 'skipped'):
        ranges = state.get(name, [])
        if type(ranges) is not list or len(ranges) > 1024:
            raise ValueError(f'Invalid checkpoint ranges: {name}')
        for item in ranges:
            if type(item) is not dict or type(item.get('offset')) is not int or \
                    type(item.get('length')) is not int or \
                    item['offset'] < 0 or item['length'] <= 0 or \
                    item['offset'] + item['length'] > size:
                raise ValueError(f'Invalid checkpoint range in {name}')
    return state


class ScanCheckpoint:
    def __init__(self, path: str | Path, *, source_token: str, size: int, sector: int,
                 minimum_interval: float = 2.0) -> None:
        self.path = Path(path)
        self.source_token, self.size, self.sector = source_token, size, sector
        self.minimum_interval = minimum_interval
        self._last = 0.0

    def save(self, state: dict, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last < self.minimum_interval:
            return
        self._last = now
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.is_symlink() or (self.path.exists() and not stat.S_ISREG(self.path.stat().st_mode)):
            raise ValueError('Unsafe checkpoint destination')
        doc = {'schema': SCHEMA, 'source_token': self.source_token,
               'size': self.size, 'sector': self.sector, 'state': state}
        # Keep bounded records. A checkpoint must not become another disk image.
        payload = json.dumps(doc, separators=(',', ':')).encode('utf-8')
        if len(payload) > 1024 * 1024:
            raise ValueError('Scan checkpoint limit exceeded')
        tmp = self.path.with_suffix(self.path.suffix + '.pending')
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                tmp.unlink()
