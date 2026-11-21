#!/usr/bin/env python3
"""Fail-closed release-promotion evidence gate; does not certify hardware itself.

Only consider records from an independently reviewed testing process. JSON
can be forged: this script validates consistency, not the authenticity or
correctness of the person who entered evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path

REQUIRED = ('bios_vm', 'uefi_vm', 'native_windows_qt', 'usb_dock_hw', 'hp_laptop_hw')


def file_sha256(path: Path) -> str:
    """Hash an ordinary finite file only — never FIFOs, devices, or symlinks."""
    path = Path(path)
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        raise OSError(f'artifact must not be a symbolic link: {path}')
    if not stat.S_ISREG(info.st_mode):
        raise OSError(f'artifact must be an ordinary file, not a special file: {path}')
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(part)
    # Reject replacement mid-hash with a non-regular node (FIFO/device/symlink).
    after = path.lstat()
    if stat.S_ISLNK(after.st_mode) or not stat.S_ISREG(after.st_mode):
        raise OSError(f'artifact changed to a non-regular file while hashing: {path}')
    return digest.hexdigest()


def evaluate(evidence: Path, artifact: Path, version: str, commit: str) -> dict:
    failures = []
    try:
        record = json.loads(Path(evidence).read_text(encoding='utf-8'))
        if not isinstance(record, dict):
            raise ValueError('evidence must be a JSON object')
    except (OSError, ValueError) as exc:
        return {'ready': False, 'failures': [f'evidence unreadable: {exc}']}
    if record.get('version') != version:
        failures.append('version mismatch')
    if not re.fullmatch(r'[0-9a-fA-F]{40}', commit):
        failures.append('source_commit must be a full 40-digit Git SHA-1')
    if record.get('source_commit') != commit:
        failures.append('source_commit mismatch')
    try:
        actual_hash = file_sha256(Path(artifact))
    except OSError as exc:
        failures.append(f'artifact missing/unreadable: {exc}')
    else:
        if record.get('artifact_sha256') != actual_hash:
            failures.append('artifact_sha256 mismatch')
    checks = record.get('checks')
    if not isinstance(checks, dict):
        checks = {}
    for key in REQUIRED:
        entry = checks.get(key)
        if not isinstance(entry, dict) or entry.get('status') != 'PASS' or not str(entry.get('evidence') or '').strip():
            failures.append(f'{key}: missing independent PASS and evidence')
    return {'ready': not failures, 'failures': failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--artifact', required=True, type=Path)
    parser.add_argument('--version', required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    result = evaluate(args.evidence, args.artifact, args.version, args.source_commit)
    for failure in result['failures']:
        print('NOT QUALIFIED:', failure)
    if result['ready']:
        print('EVIDENCE COMPLETE (independent human review still required)')
    return 0 if result['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
