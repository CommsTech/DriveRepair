"""Media-specific repair action for the Qt Repair Drive workspace.

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
    patient_write_possible: bool = False  # A separate, approved action MAY modify the original device
    hdd_region_write_candidate: bool = False  # Never inferred from filesystem repair


def choose_repair_route(device: dict | None, snapshot: dict | None = None,
                        *, smartctl_available: bool = False) -> RepairRoute:
    """Select an *operator action*, never grant write permission.

    Physical HDD repair remains separately gated by eligibility, journal,
    identity and locks. Restore/imaging is a SEPARATE workspace.
    """
    decision = readiness_next_action(device, 'carequick', snapshot,
                                     smartctl_available=smartctl_available)
    if decision['ready']:
        return RepairRoute('review', 'Review guarded HDD repair',
                           'A rotational HDD has been identified. Next: approve risk, '
                           'select separate-disk journal, recheck identity and exclusive access.', True, True)
    if not device:
        return RepairRoute('select', 'Select a drive', 'Connect and select the source drive first.')
    flash = _flash_profile(device, snapshot)
    if flash:
        kind = flash.kind.upper()
        return RepairRoute('filesystem', 'Repair filesystem on this drive',
                           f'{kind} does not support HDD magnetic-sector rewrites. '
                           'Windows CHKDSK /f can repair supported NTFS, exFAT or FAT '
                           'filesystem metadata on an identified external volume, with explicit backup/risk consent. '
                           'This is not a flash-cell repair or guarantee of healthy hardware.', True)
    if decision['action'] == 'probe':
        return RepairRoute('probe', 'Identify disk (read-only)',
                           'Check SMART/SAT and Windows storage properties automatically. '
                           'This reads only drive identity and health metadata.')
    if decision['action'] in {'identity', 'setup', 'rescue'}:
        return RepairRoute('filesystem', 'Repair filesystem on this drive',
                           'HDD sector maintenance is blocked by missing device/health evidence. '
                           'A separate on-device filesystem repair may be available for a mounted '
                           'Windows NTFS/FAT/exFAT volume after identity checks, backup acknowledgment, '
                           'and explicit approval. This does NOT fix damaged physical sectors.', True)
    return RepairRoute('filesystem', 'Inspect filesystem repair options',
                       'Select a Windows filesystem volume; raw disk repair remains independently restricted.', True)
