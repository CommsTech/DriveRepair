#!/usr/bin/env python3
"""Consent-gated host environment report and optional installer for DriveRepair.

Default mode is READ-ONLY: print what is present and what is missing. Optional
install actions require ``--approve-install`` and never run silently.

This lowers the skill bar for checking prerequisites without weakening the
policy that DriveRepair must not modify the host OS without explicit approval.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / 'desktop'


def _have_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _run(command: list[str], *, timeout: int = 240) -> dict:
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'ok': False, 'exit_code': None, 'error': str(exc)}
    return {
        'ok': done.returncode == 0,
        'exit_code': done.returncode,
        'stdout_tail': (done.stdout or '')[-800:],
        'stderr_tail': (done.stderr or '')[-800:],
    }


def report_environment() -> dict:
    smartctl = shutil.which('smartctl')
    winget = shutil.which('winget') if sys.platform == 'win32' else None
    return {
        'python': {
            'executable': sys.executable,
            'version': '%d.%d.%d' % sys.version_info[:3],
            'meets_floor': sys.version_info >= (3, 10),
        },
        'modules': {
            'driverepair_desktop': _have_module('driverepair_desktop'),
            'PySide6': _have_module('PySide6'),
            'pytest': _have_module('pytest'),
        },
        'tools': {
            'smartctl_path': smartctl,
            'smartctl_present': bool(smartctl),
            'winget_present': bool(winget),
            'pip_module': _have_module('pip'),
        },
        'paths': {
            'repository_root': str(ROOT),
            'desktop_package': str(DESKTOP),
            'desktop_present': DESKTOP.is_dir(),
        },
        'skill_paths': {
            'beginner': ('Build/run the public-beta zipapp with an existing Python 3.10+ '
                         'install; no source editable install required for read-only work.'),
            'operator': ('Install desktop[qt] for the workstation GUI, then optionally '
                         'approve smartctl setup for stronger health evidence.'),
            'developer': ('Install desktop[qt] plus pytest==8.4.2; never treat a green '
                          'local suite as hardware qualification.'),
        },
        'never_silent_install': True,
    }


def install_desktop_qt(*, approved: bool) -> dict:
    if not approved:
        raise PermissionError('Explicit --approve-install required to pip-install desktop[qt]')
    if not DESKTOP.is_dir():
        raise FileNotFoundError(f'desktop package missing: {DESKTOP}')
    return _run([sys.executable, '-m', 'pip', 'install', '-e', f'{DESKTOP}[qt]'])


def install_pytest(*, approved: bool) -> dict:
    if not approved:
        raise PermissionError('Explicit --approve-install required to pip-install pytest')
    return _run([sys.executable, '-m', 'pip', 'install', 'pytest==8.4.2'])


def install_smartctl_windows(*, approved: bool) -> dict:
    if not approved:
        raise PermissionError('Explicit --approve-install required to install smartmontools')
    # Import only when needed so the report path stays dependency-light.
    sys.path.insert(0, str(DESKTOP))
    from driverepair_desktop.dependencies import install_smartctl_windows as install_fn
    return install_fn(approved=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Emit machine-readable report/result')
    parser.add_argument('--approve-install', action='store_true',
                        help='Required consent flag for any install action')
    parser.add_argument('--install-desktop-qt', action='store_true',
                        help='pip install -e desktop[qt] (requires --approve-install)')
    parser.add_argument('--install-pytest', action='store_true',
                        help='pip install pytest==8.4.2 (requires --approve-install)')
    parser.add_argument('--install-smartctl-windows', action='store_true',
                        help='winget-install smartmontools on Windows (requires --approve-install)')
    args = parser.parse_args(argv)

    actions = []
    try:
        if args.install_desktop_qt:
            actions.append(('desktop_qt', install_desktop_qt(approved=args.approve_install)))
        if args.install_pytest:
            actions.append(('pytest', install_pytest(approved=args.approve_install)))
        if args.install_smartctl_windows:
            actions.append(('smartctl_windows', install_smartctl_windows(approved=args.approve_install)))
    except (PermissionError, FileNotFoundError, RuntimeError) as exc:
        payload = {'ok': False, 'error': str(exc), 'report': report_environment()}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print('REFUSED:', exc)
            print('Re-run with --approve-install only after you intend to modify this host.')
        return 2

    report = report_environment()
    if args.json:
        print(json.dumps({'ok': True, 'report': report, 'actions': actions}, indent=2))
        return 0 if report['python']['meets_floor'] else 1

    print('DriveRepair host environment')
    print(f"  Python: {report['python']['version']} ({report['python']['executable']})")
    print(f"  Meets 3.10+ floor: {report['python']['meets_floor']}")
    for name, present in report['modules'].items():
        print(f"  module {name}: {'yes' if present else 'MISSING'}")
    print(f"  smartctl: {report['tools']['smartctl_path'] or 'MISSING'}")
    if sys.platform == 'win32':
        print(f"  winget: {'yes' if report['tools']['winget_present'] else 'MISSING'}")
    print()
    print('Skill paths (no silent installs):')
    for level, text in report['skill_paths'].items():
        print(f"  - {level}: {text}")
    if actions:
        print()
        print('Install actions:')
        for name, result in actions:
            print(f"  - {name}: {result}")
    else:
        print()
        print('Report only. Example consented installs:')
        print(f'  {sys.executable} scripts/setup_host_environment.py --install-desktop-qt --approve-install')
        print(f'  {sys.executable} scripts/setup_host_environment.py --install-pytest --approve-install')
        if sys.platform == 'win32':
            print(f'  {sys.executable} scripts/setup_host_environment.py --install-smartctl-windows --approve-install')
    return 0 if report['python']['meets_floor'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
