"""Read-only Linux sysfs media evidence when SMART/SAT is unavailable.

A USB bridge can synthesize rotational, discard and model properties. This
report helps choose read-only rescue but NEVER authorizes HDD-style writes.
Only known whole-disk paths already admitted by the device enumerator qualify.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

from .devices import Device


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding='utf-8').strip()[:128]
    except (OSError, UnicodeError):
        return None


def linux_sysfs_snapshot(device: Device, *, root: Path | None = None) -> dict | None:
    """Read sysfs geometry for a linux:* whole disk.

    Pass an explicit ``root`` (for synthetic tests) to bypass the live-platform
    gate; production callers leave ``root`` unset so Windows never walks
    ``/sys``.
    """
    if root is None:
        if sys.platform != 'linux':
            return None
        root = Path('/sys/class/block')
    if not device.id.startswith('linux:'):
        return None
    if not device.id.endswith(device.path):
        return None
    name = Path(device.path).name
    # No partitions, symlinks, arbitrary filenames, or /dev/mapper volumes.
    if not (re.fullmatch(r'sd[a-z]+', name) or re.fullmatch(r'nvme[0-9]+n[0-9]+', name)
            or re.fullmatch(r'mmcblk[0-9]+', name)):
        return None
    path = root / name
    if not path.is_dir():
        return None
    blocks = _read(path / 'size')
    logical = _read(path / 'queue' / 'logical_block_size')
    rotational = _read(path / 'queue' / 'rotational')
    discard = _read(path / 'queue' / 'discard_max_bytes')
    try:
        if (not blocks or not logical or int(logical) != device.sector_size
                or int(blocks) * 512 != device.size_bytes):
            return None
        if rotational not in ('0', '1'):
            return None
        discard_bytes = int(discard) if discard and discard.isdecimal() else None
    except (ValueError, OverflowError):
        return None
    model = _read(path / 'device' / 'model')
    # The kernel may describe only a bridge. Never interpret this as authority.
    reported_medium = 'hdd' if rotational == '1' else 'ssd'
    return {
        'source': 'linux_sysfs_unverified', 'status': 'unknown',
        'reported_medium': reported_medium,
        'native_hdd_corrob': False,
        'smart_status_passed': None, 'temperature_c': None,
        'ata_selected_raw_attributes': [], 'nvme': {},
        'device': device.public(),
        'native_media_properties': {
            'incurs_seek_penalty': rotational == '1',
            'discard_max_bytes': discard_bytes,
            'driver_reported_model': model,
        },
        'notes': ('Linux sysfs size and sector geometry match inventory. '
                  'Rotational and discard flags are driver or bridge claims, '
                  'not physical-media or health proof. No source writes permitted.'),
    }
