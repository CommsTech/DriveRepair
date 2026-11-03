#!/usr/bin/env python3
"""Offline smoke and deny-path test of the DISTRIBUTED public-beta zipapp.

Uses only synthetic regular files and deliberately invalid device identifiers.
Never opens an actual physical drive. Exit nonzero if a raw-write entrypoint
returns success or the release policy was not the reason for rejection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def check(package: Path) -> None:
    if not package.is_file():
        raise RuntimeError(f'Public beta zipapp missing: {package}')

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(package), *args],
                              capture_output=True, text=True, timeout=30, check=False)

    # Every public command that might mutate a real disk must be stopped BEFORE
    # discovery or operating-system access. Engineering builds must fail this.
    denied = (
        ('care-image', '--image', 'INVALID-BETA-TEST'),
        ('refresh-image', '--image', 'INVALID-BETA-TEST'),
        ('care-external', '--device', 'INVALID-BETA-TEST'),
        ('refresh-external', '--device', 'INVALID-BETA-TEST'),
        ('refresh-system', '--device', 'INVALID-BETA-TEST'),
        ('optimize-volume', '--device', 'INVALID-BETA-TEST', '--letter', 'E', '--execute'),
    )
    for args in denied:
        result = run(*args)
        if result.returncode == 0 or 'in-place patient writes are unavailable' not in result.stderr.lower():
            raise RuntimeError(f'Public write-policy FAIL for {args[0]}: rc={result.returncode}; '
                               f'stderr={result.stderr[:300]!r}')

    # Prove the usable IMAGE path still works in the policy-restricted zipapp.
    with tempfile.TemporaryDirectory(prefix='driverepair_public_smoke_') as tmp:
        root = Path(tmp)
        src, out = root / 'source.img', root / 'rescued.img'
        data = (bytes(range(256)) * (1024 * 1024 // 256))
        src.write_bytes(data)
        scan = run('scan-image', '--image', str(src), '--mode', 'sample',
                   '--samples', '2', '--json')
        if scan.returncode or json.loads(scan.stdout)['status'] != 'completed':
            raise RuntimeError(f'Public image scan failed: {scan.stderr[:300]}')
        rescue = run('rescue-image', '--image', str(src), '--output', str(out), '--json')
        if rescue.returncode:
            raise RuntimeError(f'Public image rescue failed: {rescue.stderr[:300]}')
        report = run('rescue-status', '--output', str(out), '--json')
        if report.returncode or not json.loads(report.stdout).get('clean_rescue_complete'):
            raise RuntimeError(f'Public rescue journal check failed: {report.stderr[:300]}')
        if hashlib.sha256(src.read_bytes()).digest() != hashlib.sha256(out.read_bytes()).digest():
            raise RuntimeError('Public image rescue was not byte-exact on the synthetic fixture')
    print('PASS: 6 in-place patient write commands denied; synthetic scan/rescue/status/hash verified')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path, help='Path to public-beta .pyz')
    args = parser.parse_args()
    check(args.package.resolve())
