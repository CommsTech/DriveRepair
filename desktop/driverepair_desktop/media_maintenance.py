"""Unified media-aware maintenance planner (decision layer only).

Maps operator *intent* to media-appropriate operations without authorizing
patient writes. The CLI / ``media_refresh`` / ``windows_volume_repair`` engines
remain the sole write authorities. SSD/NVMe/flash physical refresh is planned
here as an opt-in future operation and stays disabled until qualification evidence
exists.

SpinRite level numbers in metadata are documentation analogues only — not a
claim of behavioral equivalence or endorsement.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import sys
from typing import Any

from .repair_readiness import _flash_profile, ui_repair_readiness
from .reliability_score import assess


@dataclass(frozen=True)
class MaintenanceOperation:
    key: str
    title: str
    intent: str
    media_classes: tuple[str, ...]
    writes_patient: bool
    enabled: bool
    risk: str
    spinrite_level_analogue: int | None
    next_step: str
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaintenancePlan:
    media_class: str
    outcome_goal: str
    primary: MaintenanceOperation
    alternatives: tuple[MaintenanceOperation, ...]
    operations: tuple[MaintenanceOperation, ...]
    assessment: dict[str, Any]
    summary: str

    def as_dict(self) -> dict[str, Any]:
        return {
            'media_class': self.media_class,
            'outcome_goal': self.outcome_goal,
            'primary': asdict(self.primary),
            'alternatives': [asdict(item) for item in self.alternatives],
            'operations': [asdict(item) for item in self.operations],
            'assessment': self.assessment,
            'summary': self.summary,
        }


def classify_media(device: dict | None, snapshot: dict | None = None) -> str:
    if not device:
        return 'unknown'
    flash = _flash_profile(device, snapshot)
    if flash is not None:
        return flash.kind  # ssd | nvme | flash
    snap = snapshot if isinstance(snapshot, dict) else {}
    medium = str(snap.get('reported_medium') or '').lower()
    if medium in {'hdd', 'cmr', 'smr', 'hdd_unknown_recording'}:
        return 'hdd' if medium == 'hdd' else medium
    bus = str(device.get('bus') or '').lower()
    if bus in {'sd', 'mmc'}:
        return 'sd'
    if bus in {'usb', 'thunderbolt', '1394', 'firewire'} and not snap:
        return 'unknown_external'
    return 'unknown'


def _ssd_refresh_enabled() -> bool:
    """Fail-closed: never enable SSD rewrite from planner metadata alone."""
    return os.environ.get('DRIVEREPAIR_ALLOW_SSD_REFRESH', '').strip() == '1'


def outcome_goal_for_job(job_kind: str | None, workspace: str | None = None) -> str:
    """Map UI job / workspace to a planner outcome goal."""
    kind = str(job_kind or '').strip().lower()
    family = str(workspace or '').strip().lower()
    if kind in {'rescue', 'rescuefull', 'resume'} or family == 'restore':
        return 'rescue_data'
    if kind in {'scanquick', 'scanfull', 'health', 'benchmark'} or family == 'diagnose':
        return 'assess_health'
    if kind in {'carequick', 'carefull', 'careresume'}:
        return 'maintain_media'
    if kind == 'winfsrepair' or family == 'fix':
        return 'make_usable'
    return 'make_usable'


def plan_media_maintenance(device: dict | None, snapshot: dict | None = None, *,
                           goal: str = 'make_usable',
                           smartctl_available: bool = False,
                           platform: str | None = None) -> MaintenancePlan:
    """Build an outcome-first maintenance plan for the selected medium.

    ``goal`` is one of: make_usable | rescue_data | assess_health | maintain_media.
    """
    platform = platform or sys.platform
    media = classify_media(device, snapshot)
    assessment = assess(snapshot if isinstance(snapshot, dict) else None)
    ops: list[MaintenanceOperation] = []

    ops.append(MaintenanceOperation(
        key='inspect_readonly',
        title='Inspect without changing the drive',
        intent='Detect problems and map readable vs troubled regions',
        media_classes=('hdd', 'cmr', 'smr', 'ssd', 'nvme', 'flash', 'sd', 'unknown', 'unknown_external'),
        writes_patient=False,
        enabled=bool(device),
        risk='none',
        spinrite_level_analogue=1,
        next_step='Run Diagnose / quick surface check (read-only).',
        blockers=() if device else ('Select a drive first.',),
    ))

    if platform == 'win32':
        ops.append(MaintenanceOperation(
            key='filesystem_repair',
            title='Repair filesystem metadata on Windows',
            intent='Fix NTFS/exFAT/FAT metadata on a mounted external volume',
            media_classes=('hdd', 'cmr', 'smr', 'ssd', 'nvme', 'flash', 'sd', 'unknown_external'),
            writes_patient=True,
            enabled=bool(device),
            risk='moderate',
            spinrite_level_analogue=None,
            next_step='Choose Repair filesystem on this drive; confirm volume binding and backup.',
            blockers=() if device else ('Select a drive first.',),
        ))

    ops.append(MaintenanceOperation(
        key='rescue_image',
        title='Rescue readable data to a separate image',
        intent='Preserve recoverable bytes before any maintenance writes',
        media_classes=('hdd', 'cmr', 'smr', 'ssd', 'nvme', 'flash', 'sd', 'unknown', 'unknown_external'),
        writes_patient=False,
        enabled=bool(device),
        risk='low',
        spinrite_level_analogue=2,
        next_step='Open Restore / rescue workflow to a separate healthy disk.',
        blockers=() if device else ('Select a drive first.',),
    ))

    ops.append(MaintenanceOperation(
        key='lost_partition_scan',
        title='Scan for lost or orphaned partitions',
        intent='Read MBR/GPT and boot signatures without rewriting tables',
        media_classes=('hdd', 'cmr', 'smr', 'ssd', 'nvme', 'flash', 'sd', 'unknown', 'unknown_external'),
        writes_patient=False,
        enabled=bool(device),
        risk='none',
        spinrite_level_analogue=1,
        next_step='Run scan-lost-partitions (CLI) or image first, then TestDisk for structural writes.',
        blockers=() if device else ('Select a drive first.',),
    ))

    ops.append(MaintenanceOperation(
        key='weak_region_reread',
        title='Bounded reread of troubled sectors',
        intent='Retry slow/failed offsets without rewriting the medium',
        media_classes=('hdd', 'cmr', 'smr', 'ssd', 'nvme', 'flash', 'sd'),
        writes_patient=False,
        enabled=bool(device),
        risk='low',
        spinrite_level_analogue=2,
        next_step='After a scan with recorded failures, use Address scan errors (read-only).',
        blockers=() if device else ('Select a drive first.',),
    ))

    hdd_ready, hdd_reason = ui_repair_readiness(device, 'carequick', snapshot)
    ops.append(MaintenanceOperation(
        key='hdd_region_refresh',
        title='Guarded HDD magnetic-region refresh',
        intent='Rewrite only consistently readable weak HDD regions after consent',
        media_classes=('hdd', 'cmr', 'smr', 'hdd_unknown_recording'),
        writes_patient=True,
        enabled=bool(hdd_ready and media in {'hdd', 'cmr', 'smr', 'hdd_unknown_recording'}),
        risk='high',
        spinrite_level_analogue=3,
        next_step='Review guarded HDD maintenance with separate journal and identity recheck.',
        blockers=() if hdd_ready else (hdd_reason,),
    ))

    ops.append(MaintenanceOperation(
        key='verify_after_maintenance',
        title='Verification read after maintenance',
        intent='Confirm post-write readability; does not invent missing data',
        media_classes=('hdd', 'cmr', 'smr', 'ssd', 'nvme', 'flash'),
        writes_patient=False,
        enabled=bool(device),
        risk='low',
        spinrite_level_analogue=4,
        next_step='Re-run surface check / benchmark after any approved write job.',
        blockers=() if device else ('Select a drive first.',),
    ))

    ssd_refresh_on = _ssd_refresh_enabled()
    ops.append(MaintenanceOperation(
        key='qualified_flash_refresh',
        title='Qualified solid-state data refresh (research)',
        intent='Selectively rewrite successfully read logical data on SSD/NVMe/flash',
        media_classes=('ssd', 'nvme', 'flash'),
        writes_patient=True,
        enabled=bool(ssd_refresh_on and media in {'ssd', 'nvme', 'flash'} and device),
        risk='high',
        spinrite_level_analogue=3,
        next_step=('Disabled until independent qualification evidence exists. '
                   'Set DRIVEREPAIR_ALLOW_SSD_REFRESH=1 only on sacrificial media in a lab.'),
        blockers=() if ssd_refresh_on else (
            'Solid-state physical refresh is not enabled in this build.',
            'NAND wear, TRIM, and controller behavior differ from HDD rewrites.',
        ),
    ))

    ops.append(MaintenanceOperation(
        key='intensive_pattern_cycle',
        title='Intensive inverted pattern cycle',
        intent='SpinRite Level-5 analogue: pattern write/verify/restore research path',
        media_classes=('hdd', 'cmr', 'smr'),
        writes_patient=True,
        enabled=False,
        risk='extreme',
        spinrite_level_analogue=5,
        next_step='Not offered. Requires separate lab qualification and disposable media.',
        blockers=('Intensive pattern cycles are not enabled.',),
    ))

    # Filter to media-relevant operations while keeping inspect/rescue visible.
    relevant = [op for op in ops if media in op.media_classes or op.key in {'inspect_readonly', 'rescue_image'}]
    if goal == 'rescue_data':
        preferred_keys = ('rescue_image', 'weak_region_reread', 'inspect_readonly')
    elif goal == 'assess_health':
        preferred_keys = ('inspect_readonly', 'verify_after_maintenance', 'rescue_image')
    elif goal == 'maintain_media':
        preferred_keys = ('hdd_region_refresh', 'filesystem_repair', 'qualified_flash_refresh',
                          'inspect_readonly', 'rescue_image')
    else:  # make_usable
        preferred_keys = ('filesystem_repair', 'hdd_region_refresh', 'rescue_image',
                          'inspect_readonly', 'weak_region_reread')

    ordered: list[MaintenanceOperation] = []
    for key in preferred_keys:
        for op in relevant:
            if op.key == key and op not in ordered:
                ordered.append(op)
    for op in relevant:
        if op not in ordered:
            ordered.append(op)

    enabled = [op for op in ordered if op.enabled]
    primary = enabled[0] if enabled else ordered[0]
    alternatives = tuple(op for op in ordered if op.key != primary.key)[:4]

    if not device:
        summary = 'Select an external drive to see what DriveRepair can do for that media type.'
    elif primary.key == 'filesystem_repair':
        summary = (f'{media.upper()}: start with filesystem metadata repair on Windows, '
                   f'or rescue an image first if the data matters more than reuse.')
    elif primary.key == 'hdd_region_refresh':
        summary = ('Rotational HDD with enough evidence for a *review* of guarded region refresh. '
                   'This still requires journal, locks, identity recheck and explicit consent.')
    elif primary.key == 'rescue_image':
        summary = (f'{media.upper()}: physical maintenance is blocked or unsuitable. '
                   f'Rescue readable data to a separate disk; replacement may be required.')
    else:
        summary = f'{media.upper()}: {primary.title}. {primary.next_step}'

    if assessment.get('score') is None and assessment.get('band'):
        summary += f" Health index: {assessment.get('band')} ({assessment.get('confidence', 'n/a')} confidence)."

    return MaintenancePlan(
        media_class=media,
        outcome_goal=goal,
        primary=primary,
        alternatives=alternatives,
        operations=tuple(ordered),
        assessment={
            'score': assessment.get('score'),
            'band': assessment.get('band'),
            'confidence': assessment.get('confidence'),
            'reasons': assessment.get('reasons', [])[:6],
            'smartctl_available': smartctl_available,
        },
        summary=summary,
    )
