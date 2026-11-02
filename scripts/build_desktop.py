#!/usr/bin/env python3
"""Offline-safe Python packaging entry point (tests + pyz, optional wheel).

All build/test steps operate on files and synthetic fixtures; never touch disks.
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipapp
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DESKTOP = REPO / 'desktop'
VERSION = '0.3.3b6'


def command(args: list[str], cwd: Path = DESKTOP) -> None:
    print('+', ' '.join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def build(include_wheel: bool = True) -> list[Path]:
    dist = REPO / 'dist'
    dist.mkdir(exist_ok=True)
    command([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
    command([sys.executable, '-m', 'compileall', '-q', 'driverepair_desktop'])
    outputs = []
    with tempfile.TemporaryDirectory(prefix='driverepair_build_') as temporary:
        payload = Path(temporary)
        shutil.copytree(DESKTOP / 'driverepair_desktop', payload / 'driverepair_desktop',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        outfile = dist / f'DriveRepair-{VERSION}.pyz'
        zipapp.create_archive(payload, outfile, interpreter='/usr/bin/env python3',
                              main='driverepair_desktop.cli:main', compressed=True)
        outputs.append(outfile)
    command([sys.executable, str(outputs[0]), '--help'], cwd=REPO)
    if include_wheel:
        command([sys.executable, '-m', 'pip', 'wheel', '.', '--no-deps',
                 '--no-build-isolation', '-w', str(dist)])
        outputs.extend(dist.glob(f'driverepair_desktop-{VERSION}-*.whl'))
    for path in outputs:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f'{path.name}  sha256:{digest}', flush=True)
    return outputs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-wheel', action='store_true',
                        help='Build zipapp only when Python wheel build tooling is unavailable')
    opts = parser.parse_args()
    build(not opts.no_wheel)
