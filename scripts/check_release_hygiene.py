#!/usr/bin/env python3
"""Fail CI on stale active version references; leave historical change logs alone.

Compatible with the desktop package floor (Python >=3.10): version parsing does
not require tomllib (3.11+). Prefer stdlib tomllib when present.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


def _load_project_version(pyproject: Path) -> str:
    text = pyproject.read_text(encoding='utf-8')
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:  # pragma: no cover - exercised on 3.10 hosts
        try:
            import tomli as tomllib  # type: ignore
        except ModuleNotFoundError:
            match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', text)
            if not match:
                raise ValueError(f'{pyproject}: missing project version') from None
            return match.group(1)
    data = tomllib.loads(text)
    version = data.get('project', {}).get('version')
    if not isinstance(version, str) or not version:
        raise ValueError(f'{pyproject}: missing project.version')
    return version


def check_repository(root: Path) -> dict:
    root = Path(root)
    version = _load_project_version(root / 'desktop' / 'pyproject.toml')
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
    if sys.version_info < (3, 10):
        print('FAIL: Python 3.10+ is required for release hygiene checks', file=sys.stderr)
        return 2
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
