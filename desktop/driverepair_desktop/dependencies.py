"""Local-only prerequisite detection and consent-based system package setup.

Never download from an arbitrary URL or silently elevate/install binaries.
A missing optional tool must not make disk health appear good.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def smartctl_path() -> str | None:
    try:
        found = shutil.which('smartctl')
    except (AttributeError, OSError):
        # Unit-test/platform emulation must not break path discovery.
        found = None
    if found:
        return found
    if sys.platform == 'win32':
        for root in (os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')):
            if root:
                candidate = Path(root) / 'smartmontools' / 'bin' / 'smartctl.exe'
                if candidate.is_file():
                    return str(candidate)
    return None


def detect() -> dict:
    smartctl = smartctl_path()
    tools = {'smartctl': smartctl, 'fls': shutil.which('fls'),
             'icat': shutil.which('icat'), 'e2fsck': shutil.which('e2fsck')}
    return {'platform': sys.platform,
            'smart_health_available': bool(smartctl),
            'tools': {key: ('available' if path else 'optional_missing')
                      for key, path in tools.items()},
            'install_support': ('winget' if sys.platform == 'win32' and shutil.which('winget')
                                else 'manual'),
            'warning': ('' if smartctl else
                        'SMART data unavailable. Disk health is UNKNOWN until smartmontools can read it.'),
            'notes': 'Missing optional forensic tools do not disable basic read-only scanning.'}


def install_smartctl_windows(*, approved: bool,
                             run=subprocess.run, which=shutil.which) -> dict:
    if sys.platform != 'win32':
        raise RuntimeError('Windows package installation is only available on Windows')
    if not approved:
        raise PermissionError('Explicit user approval required to install smartmontools')
    winget = which('winget')
    if not winget:
        raise RuntimeError('Windows Package Manager (winget) is missing; use official smartmontools installer')
    # Exact package ID, no shell; winget owns publisher validation and user prompts.
    command = [winget, 'install', '--id', 'smartmontools.smartmontools', '--exact',
               '--source', 'winget', '--disable-interactivity',
               '--accept-source-agreements', '--accept-package-agreements']
    done = run(command, capture_output=True, text=True, timeout=240)
    return {'status': 'installer_completed' if done.returncode == 0 else 'installer_failed',
            'exit_code': done.returncode,
            'notes': ('Restart DriveRepair or refresh prerequisites after installer finishes. '
                      'No device firmware or disk sectors were changed.')}
