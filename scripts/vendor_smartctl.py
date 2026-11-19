#!/usr/bin/env python3
"""Stage an operator-supplied upstream smartctl.exe for offline DriveRepair builds.

Acquire smartmontools from its official publisher, verify upstream PGP
signature/provenance *before* using this script, and include GPLv2 compliance
materials when distributing. We do not fetch or install executable code at
runtime. Output folder is a companion to .pyz: dist/tools/smartmontools/.
"""
import argparse
import hashlib
import shutil
from pathlib import Path


def stage(executable: Path, dest: Path) -> Path:
    if executable.name.lower() != 'smartctl.exe' or not executable.is_file():
        raise ValueError('Provide an extracted official smartctl.exe; no installer EXE')
    if dest.exists():
        raise FileExistsError('Destination exists; staged executable must not be overwritten')
    dest.mkdir(parents=True, exist_ok=False)
    dst = dest / 'smartctl.exe'
    shutil.copyfile(executable, dst)
    (dest / 'smartctl.sha256').write_text(hashlib.sha256(dst.read_bytes()).hexdigest() + '  smartctl.exe\n')
    (dest / 'SOURCE_AND_LICENSE.txt').write_text(
        'smartmontools / smartctl (GPL-2.0-or-later, upstream documentation controls).\n'
        'Official upstream: https://github.com/smartmontools/smartmontools\n'
        'The distributor must supply the corresponding source/license notices and verify\n'
        'upstream binary origin/signature before shipping. Local SHA-256 only detects\n'
        'alteration after staging; it does NOT authenticate the publisher.\n')
    return dst


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('official_smartctl_exe', type=Path)
    p.add_argument('--destination', type=Path, default=Path('dist/tools/smartmontools'))
    args = p.parse_args()
    print(stage(args.official_smartctl_exe, args.destination))
