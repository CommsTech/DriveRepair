#!/usr/bin/env python3
"""Fail CI on stale active version references; leave historical change logs alone."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import tomllib


def check_repository(root: Path) -> dict:
    root = Path(root)
    version = tomllib.loads((root / 'desktop' / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    errors = []
    package_init = root / 'desktop' / 'driverepair_desktop' / '__init__.py'
    if package_init.is_file():
        module_text = package_init.read_text(encoding='utf-8')
        if f'__version__ = "{version}"' not in module_text:
            errors.append(f'desktop/driverepair_desktop/__init__.py: expected {version}')
    status = (root / 'status.md').read_text(encoding='utf-8')
    if not status.startswith(f'**{version}**'):
        errors.append(f'status.md: current status must begin with **{version}**')
    release = (root / 'docs' / 'RELEASE_STATUS.md').read_text(encoding='utf-8')
    if not any(line.startswith(f'# DriveRepair release status — v{version}') for line in release.splitlines()[:3]):
        errors.append(f'docs/RELEASE_STATUS.md: active release header must be v{version}')
    readme = (root / 'README.md').read_text(encoding='utf-8')
    for match in re.finditer(r'dist/DriveRepair-(\d+\.\d+\.\d+b\d+)-[^\s`"\']+\.pyz', readme):
        if match.group(1) != version:
            line = readme.count('\n', 0, match.start()) + 1
            errors.append(f'README.md:{line}: active CLI example is {match.group(1)}, expected {version}')
    return {'version': version, 'errors': errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = check_repository(args.root)
    if result['errors']:
        for error in result['errors']:
            print('FAIL:', error)
        return 1
    print(f"PASS: DriveRepair {result['version']} active docs and examples agree")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
