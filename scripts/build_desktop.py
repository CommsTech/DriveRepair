#!/usr/bin/env python3
"""Offline-safe Python packaging entry point (tests + pyz, optional wheel).

All build/test steps operate on files and synthetic fixtures; never touch disks.
"""
import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipapp
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DESKTOP = REPO / 'desktop'
# Packaging version follows the desktop project metadata, avoiding CI artifact drift.
_project_meta = (DESKTOP / 'pyproject.toml').read_text(encoding='utf-8')
_version_match = re.search(r'^version\s*=\s*"([^"]+)"', _project_meta, re.MULTILINE)
if _version_match is None:
    raise RuntimeError('Missing desktop project version')
VERSION = _version_match.group(1)


def command(args: list[str], cwd: Path = DESKTOP) -> None:
    print('+', ' '.join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def build(include_wheel: bool = True, *, public_beta: bool = False, repair_beta: bool = False,
          recovery_iso: str | None = None) -> list[Path]:
    if public_beta and repair_beta:
        raise ValueError('Choose one release channel')
    dist = REPO / 'dist'
    dist.mkdir(exist_ok=True)
    command([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
    command([sys.executable, '-m', 'compileall', '-q', 'driverepair_desktop'])
    outputs = []
    with tempfile.TemporaryDirectory(prefix='driverepair_build_') as temporary:
        payload = Path(temporary)
        shutil.copytree(DESKTOP / 'driverepair_desktop', payload / 'driverepair_desktop',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        if public_beta:
            policy_file = payload / 'driverepair_desktop' / 'release_policy.py'
            current = policy_file.read_text(encoding='utf-8')
            marker = 'PUBLIC_BETA_IMAGE_ONLY = False'
            if current.count(marker) != 1:
                raise RuntimeError('Public beta policy marker missing or ambiguous')
            policy_file.write_text(current.replace(marker, 'PUBLIC_BETA_IMAGE_ONLY = True'), encoding='utf-8')
        if repair_beta:
            policy_file = payload / 'driverepair_desktop' / 'release_policy.py'
            current = policy_file.read_text(encoding='utf-8')
            marker = 'REPAIR_BETA_GUARDED = False'
            if current.count(marker) != 1:
                raise RuntimeError('Repair-beta policy marker missing or ambiguous')
            policy_file.write_text(current.replace(marker, 'REPAIR_BETA_GUARDED = True'), encoding='utf-8')
        suffix = '-repair-beta' if repair_beta else '-public-beta' if public_beta else ''
        outfile = dist / f'DriveRepair-{VERSION}{suffix}.pyz'
        zipapp.create_archive(payload, outfile, interpreter='/usr/bin/env python3',
                              main='driverepair_desktop.cli:main', compressed=True)
        outputs.append(outfile)
    command([sys.executable, str(outputs[0]), '--help'], cwd=REPO)
    if recovery_iso:
        # A distributable Windows USB creator must have an actual image sidecar.
        # The build kit ZIP and .pyz alone are NOT boot media. Still require
        # signed release provenance and independent boot testing before publish.
        sys.path.insert(0, str(DESKTOP))
        from driverepair_desktop.usb_flash import inspect_hybrid_iso
        info = inspect_hybrid_iso(recovery_iso)
        source = Path(info['path'])
        sidecar = dist / 'images' / 'DriveRepair-Live-amd64.iso'
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        if sidecar.resolve() != source.resolve():
            if sidecar.exists():
                raise FileExistsError('Recovery ISO distribution path already exists; refusing silent replacement')
            shutil.copyfile(source,sidecar)
        sha = hashlib.sha256()
        with sidecar.open('rb') as handle:
            for chunk in iter(lambda: handle.read(4*1024*1024),b''):
                sha.update(chunk)
        checksum = sidecar.with_suffix('.iso.sha256')
        checksum.write_text(f'{sha.hexdigest()}  {sidecar.name}\n',encoding='ascii')
        outputs.extend([sidecar, checksum])
        print('Recovery ISO sidecar staged: '+str(sidecar),flush=True)
        print('UNVERIFIED: ISO markers do not prove BIOS/UEFI bootability.',flush=True)
    if include_wheel and not public_beta:
        command([sys.executable, '-m', 'pip', 'wheel', '.', '--no-deps',
                 '--no-build-isolation', '-w', str(dist)])
        outputs.extend(dist.glob(f'driverepair_desktop-{VERSION}-*.whl'))
    for path in outputs:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f'{path.name}  sha256:{digest}', flush=True)
    return outputs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-beta', action='store_true',
                        help='Build image-first zipapp with all in-place patient writes disabled')
    parser.add_argument('--repair-beta', action='store_true',
                        help='Build hardware-repair beta: HDD-only guided journaled writes with strict gates')
    parser.add_argument('--recovery-iso', metavar='HYBRID_ISO',
                        help='Stage an existing validated DriveRepair hybrid ISO beside the zipapp for auto-selection; never builds the ISO')
    parser.add_argument('--no-wheel', action='store_true',
                        help='Build zipapp only when Python wheel build tooling is unavailable')
    opts = parser.parse_args()
    build(not opts.no_wheel, public_beta=opts.public_beta, repair_beta=opts.repair_beta,
          recovery_iso=opts.recovery_iso)
