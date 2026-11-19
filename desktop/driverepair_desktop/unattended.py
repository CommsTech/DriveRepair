"""Safe, serialized read-only multi-device rescue planning.

The actual CLI still performs the authoritative source/destination ancestry,
identity and capacity verification at the time each job starts.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re


def plan_rescue_batch(devices: list[dict], destination: str, *, free_bytes: int | None = None) -> list[dict]:
    target = Path(destination).resolve(strict=True)
    if not target.is_dir():
        raise ValueError('Choose an existing destination folder on separate healthy storage')
    if not devices:
        raise ValueError('Select at least one source drive')
    if free_bytes is None:
        free_bytes = __import__('shutil').disk_usage(target).free
    plans = []
    seen_ids = set()
    seen_fingerprints = set()
    needed = 0
    for d in devices:
        device_id, fingerprint = d.get('id'), d.get('identity_hint')
        size = d.get('size_bytes')
        if (not isinstance(device_id, str) or not device_id or
                not isinstance(fingerprint, str) or len(fingerprint) < 8 or
                type(size) is not int or size <= 0):
            raise ValueError('Each drive must have a fresh device ID, fingerprint and positive capacity')
        if device_id in seen_ids or fingerprint in seen_fingerprints:
            raise ValueError('A drive was selected twice or has an ambiguous fingerprint')
        seen_ids.add(device_id)
        seen_fingerprints.add(fingerprint)
        model = re.sub(r'[^A-Za-z0-9-]+', '-', str(d.get('model') or 'drive')).strip('-')[:35] or 'drive'
        token = hashlib.sha256((fingerprint + ':' + str(size)).encode()).hexdigest()[:12]
        output = target / f'DriveRepair-{model}-{token}.img'
        if output.exists() or output.is_symlink() or Path(str(output) + '.rescue.json').exists():
            raise FileExistsError(f'Existing output or rescue journal: {output.name}')
        # Reserve 5% headroom and filesystem metadata; actual safety check is
        # made by the CLI immediately before creating any image.
        needed += size
        plans.append({'device_id': device_id, 'fingerprint': fingerprint, 'size_bytes': size,
                      'model': str(d.get('model') or 'Unknown'), 'output': str(output),
                      'status': 'PENDING'})
    if free_bytes < needed + max(512 * 1024 * 1024, needed // 20):
        raise ValueError('Not enough free space for all full-disk images plus safety headroom')
    return plans


def batch_manifest_path(destination: str) -> Path:
    """Keep queue metadata AWAY from the patient and unverified destination.

    The engine validates destination ancestry before writing the image. A
    manifest saved into the destination folder *before* that check could itself
    alter the source media, which would violate our read-only rescue promise.
    """
    import secrets
    from datetime import datetime, timezone
    import tempfile
    if os.name == 'nt':
        home = Path(os.environ.get('LOCALAPPDATA') or tempfile.gettempdir())
    else:
        home = Path(os.environ.get('XDG_STATE_HOME') or Path.home()/'.local'/'state')
    folder = home / 'DriveRepair' / 'batches'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return folder / f'batch-{timestamp}-{secrets.token_hex(4)}.json'


def store_manifest(path: Path, items: list[dict]) -> None:
    """Create a private initial manifest; never overwrite old operator evidence."""
    payload = {'version': 1, 'mode': 'serialized_read_only_rescue', 'jobs': items,
               'note': 'Not a repair authorization. Read-only source; validate every rescue image separately.'}
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_BINARY', 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def append_batch_event(manifest: Path, event: dict) -> None:
    """Append-only durable outcomes; preserves original manifest for recovery."""
    if manifest is None or not manifest.is_file():
        raise ValueError('A durable batch manifest is required')
    path=Path(str(manifest)+'.events.jsonl')
    flags=os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os,'O_BINARY',0)
    fd=os.open(path, flags, 0o600)
    with os.fdopen(fd, 'a', encoding='utf-8') as f:
        f.write(json.dumps(event, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())
