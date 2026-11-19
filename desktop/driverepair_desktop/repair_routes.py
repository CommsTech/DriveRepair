"""Media-specific primary action for the Qt Repair & Restore workspace.

An active primary action does not imply permission to write to patient media.
The guard in ``start_job`` and the CLI remain independent.  SSD and removable
flash can undergo data recovery and copy-only filesystem repair, not magnetic
HDD refresh.  This module contains no I/O so its decisions are testable.
"""
from __future__ import annotations

from dataclasses import dataclass

from .repair_readiness import readiness_next_action, _flash_profile


@dataclass(frozen=True)
class RepairRoute:
    action: str
    button: str
    explanation: str
    patient_write_possible: bool = False


def choose_repair_route(device: dict | None, snapshot: dict | None = None,
                        *, smartctl_available: bool = False) -> RepairRoute:
    """Select an *operator action*, never grant write permission.

    Physical HDD repair remains separately gated by eligibility, journal,
    identity and locks, while non-HDD drives get an actual recovery entry point.
    """
    decision = readiness_next_action(device, 'carequick', snapshot,
                                     smartctl_available=smartctl_available)
    if decision['ready']:
        return RepairRoute('review', 'Review guarded HDD repair',
                           'A rotational HDD has been identified. Next: approve risk, '
                           'select separate-disk journal, recheck identity and exclusive access.', True)
    if not device:
        return RepairRoute('select', 'Select a drive', 'Connect and select the source drive first.')
    flash = _flash_profile(device, snapshot)
    if flash:
        kind = flash.kind.upper()
        return RepairRoute('rescue', f'Prepare {kind} recovery',
                           f'{kind} does not support HDD-style sector rewrites. '
                           'Set up a recovery image on different healthy storage, then '
                           'recover files or repair a supported filesystem on a NEW copy.')
    if decision['action'] == 'probe':
        return RepairRoute('probe', 'Identify disk (read-only)',
                           'Check SMART/SAT and Windows storage properties automatically. '
                           'This reads only drive identity and health metadata.')
    if decision['action'] in {'identity', 'setup', 'rescue'}:
        return RepairRoute('rescue', 'Set up recovery image',
                           'The external disk cannot currently satisfy the physical-write '
                           'identity/health checks. Save readable bytes to a separate image; '
                           'try another known-compatible SATA/USB bridge for optional HDD maintenance.')
    return RepairRoute('rescue', 'Set up recovery image',
                       'Preserve readable bytes on separate storage before other maintenance.')
