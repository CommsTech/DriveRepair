"""Qt workstation presentation contract, independent of a Qt installation.

Every state description here is deliberately an operator-facing *claim about
workflow*, not an inferred statement about media health or recovery success.
Keep UI copy and gating testable without creating native widgets.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Workspace:
    title: str
    subtitle: str
    operation: str
    risk: str
    next_step: str


WORKSPACES = {
    'check': Workspace(
        'Diagnose a drive',
        'Read-only evidence first. A passing scan does not certify file integrity or drive life.',
        'Read-only diagnosis', 'No planned writes to source',
        'Verify the drive model and serial suffix, then choose a diagnostic check.'),
    'recover': Workspace(
        'Restore data',
        'Save readable data onto another healthy disk before attempting invasive work.',
        'Read-only source', 'Writes only to a new destination image',
        'Select your external source drive. A destination image is chosen when you start.'),
    'fix': Workspace(
        'Repair drive',
        'On-device logical filesystem repair and eligible HDD region maintenance. Restore is separate.',
        'Experimental guarded writes', 'Writes can alter or lose data; confirm the specific method',
        'Choose a supported repair method; approve any on-device changes explicitly.'),
}

IMAGE_OPERATIONS = frozenset({'rescueimage'})
EXPERIMENTAL_OPERATIONS = frozenset({'carequick', 'carefull', 'careresume', 'winfsrepair'})

# A fast source can emit thousands of progress events per second. Repainting
# every one of them starves the UI thread and makes the window feel stuck.
PROGRESS_RENDER_INTERVAL_SECONDS = 0.1


def should_render_progress(*, now: float, last_render_at: float | None,
                           phase: str | None, last_phase: str | None,
                           terminal: bool = False,
                           min_interval: float = PROGRESS_RENDER_INTERVAL_SECONDS) -> bool:
    """Coalesce high-rate progress events into a steady visual cadence.

    Phase transitions and terminal events always render immediately; only the
    repetitive in-phase updates are rate limited. Dropping frames must never
    drop state: the caller keeps the newest event and renders it on the next
    tick, so the final displayed value is still the latest one.
    """
    if terminal or last_render_at is None or phase != last_phase:
        return True
    return (now - last_render_at) >= min_interval


def operation_family(kind: str | None) -> str:
    if kind in EXPERIMENTAL_OPERATIONS:
        return 'fix'
    if kind in {'rescue', 'rescueimage'}:
        return 'recover'
    return 'check'


def can_start(kind: str | None, *, device_selected: bool, image_exists: bool,
              running: bool, public_beta: bool) -> tuple[bool, str]:
    """Only controls button availability; engine revalidates all inputs.

    Never turn this UI convenience gate into disk-write authorization.
    """
    if running:
        return False, 'An operation is already running. Stop it safely before starting another.'
    if kind == 'capacity' and public_beta:
        return False, 'USB capacity spot tests temporarily write to the source and are unavailable in the read-only public build.'
    if kind in EXPERIMENTAL_OPERATIONS and public_beta:
        return False, 'In-place repair is unavailable in the image-first public beta.'
    if kind in IMAGE_OPERATIONS:
        if not image_exists:
            return False, 'Choose an existing disk image to recover from.'
        return True, 'Ready to choose a NEW destination image on another healthy disk.'
    if not device_selected:
        return False, 'Connect and select the external source drive to continue.'
    if kind == 'rescue':
        return True, 'Ready to choose a NEW destination image on another healthy disk.'
    if kind == 'winfsrepair':
        return True, 'Ready to select a mounted Windows volume on this disk and review the write risks.'
    if kind in EXPERIMENTAL_OPERATIONS:
        return True, 'Ready for required safety review, fingerprint confirmation and journaling.'
    return True, 'Ready to start read-only diagnostics.'


def operation_impact(kind: str | None) -> tuple[str, str]:
    if kind == 'winfsrepair':
        return ('ON-DEVICE FILESYSTEM WRITE', 'CHKDSK /f can modify filesystem metadata and lose damaged file records. Backup and explicit approval required; no physical media repair.')
    if kind == 'capacity':
        return ('WRITES / RESTORES SOURCE', 'High-risk test. Temporarily writes sampled USB regions and tries to restore originals; full backup required.')
    if kind in IMAGE_OPERATIONS:
        return ('READ-ONLY SOURCE', 'Source image is read-only; a separate NEW image receives the recovered bytes.')
    family = operation_family(kind)
    if family == 'recover':
        return ('READ-ONLY SOURCE', 'Source drive is read-only; output must be on another healthy physical disk.')
    if family == 'fix':
        return ('EXPERIMENTAL WRITE', 'Source may be rewritten only after explicit authorization and engine safeguards.')
    return ('READ-ONLY', 'Diagnostics read the source without attempting media rewrites.')


def operator_summary(*, operation: str, device: dict | None, result: str,
                     explanation: str, progress: str, errors: str,
                     observed_coverage: str) -> str:
    """Compact human-readable status: never infer a healthy disk or successful repair."""
    device = device or {}
    model = str(device.get('model') or 'No external device selected').replace('\n', ' ').strip()
    bus = str(device.get('bus') or 'unknown').replace('\n', ' ')
    suffix = str(device.get('serial_suffix') or 'not available').replace('\n', ' ')
    return '\n'.join((
        'DriveRepair — local operator summary',
        f'Operation: {operation}',
        f'Device: {model} | Bus: {bus} | Serial suffix: {suffix}',
        f'Outcome: {result}',
        f'Details: {explanation}',
        f'Planned work progress: {progress}',
        f'Failed read requests (not confirmed bad sectors): {errors}',
        f'Measured successful read coverage: {observed_coverage}',
        'Interpretation: completed operations and readable regions do not certify file integrity or media lifespan.',
    ))

@dataclass(frozen=True)
class RepairPresentation:
    heading: str
    explanation: str
    next_action: str
    status_label: str
    complete_with_unresolved: bool


def repair_presentation(result: dict, *, exit_code: int) -> RepairPresentation | None:
    """Interpret the machine result without using process exit code as a health score.

    A successful *transaction* is not successful data restoration. In
    particular partial_repair_unresolved_data exits nonzero by design and must
    not collapse to a generic 'failed (2)' user message.
    """
    if not isinstance(result, dict):
        return None
    state = str(result.get('status') or '')
    if state not in {
        'partial_repair_unresolved_data', 'completed_targeted_refresh',
        'repair_postverify_failed', 'repair_postverify_unavailable',
        'repair_health_deteriorated', 'repair_incomplete',
        'repair_stopped_safely', 'completed_no_refresh_needed',
    }:
        return None
    scan = result.get('scan') if isinstance(result.get('scan'),dict) else {}
    repair = result.get('repair') if isinstance(result.get('repair'),dict) else {}
    verification = result.get('postverification') if isinstance(result.get('postverification'),dict) else {}
    attempted = scan.get('read_error_chunks')
    attempts = (f'{attempted} failed read attempts in the scan' if type(attempted) is int
                else 'read-failure count unavailable')
    written = max(0,int(repair.get('rewritten_bytes') or 0))
    independently_verified = (max(0,int(verification.get('verified_bytes') or 0))
                              if verification.get('status') == 'postverify_passed' else 0)
    def size(n: int) -> str:
        for unit in ('B','KiB','MiB','GiB','TiB'):
            if n < 1024 or unit == 'TiB':
                return f'{n:,.0f} {unit}' if unit == 'B' else f'{n:,.2f} {unit}'
            n /= 1024
        return 'unknown'
    evidence = (f'{size(written)} rewritten; {size(independently_verified)} independently reread '
                f'and digest-matched' if verification.get('status') == 'postverify_passed'
                else f'{size(written)} reported rewritten; independent verification is NOT confirmed '
                     f'({verification.get("status", "not reported")})')
    rescue = ('Save a recovery image to separate healthy storage. Investigate unresolved '
              'ranges on the image, inspect SMART/USB connection evidence, and replace '
              'the drive if errors recur. Do not repeat writes automatically.')
    if state == 'partial_repair_unresolved_data':
        return RepairPresentation('Partial maintenance · unreadable data remains',
            f'{evidence}. {attempts}. Some regions remain unresolved or untested; '
            'rewriting readable bytes did not reconstruct unreadable data.', rescue,
            'PARTIAL · NOT REPAIRED',True)
    if state == 'completed_targeted_refresh':
        return RepairPresentation('Targeted rewrite verified · drive health NOT certified',
            f'{evidence}. {attempts}. A readback match does not demonstrate '
            'that marginal media is reliable or recover missing files.',
            'Back up immediately, run a manufacturer-supported long test when safe, '
            'and compare SMART trends before considering reuse.',
            'REWRITE VERIFIED · MONITOR',False)
    if state in {'repair_postverify_failed','repair_postverify_unavailable','repair_health_deteriorated'}:
        return RepairPresentation('Repair result not independently verified',
            f'{evidence}. {attempts}. Media condition or required readback evidence '
            'does not support a successful repair claim.',rescue,
            'UNVERIFIED · ATTENTION',True)
    if state == 'completed_no_refresh_needed':
        return RepairPresentation('No eligible regions rewritten',
            f'{attempts}. This operation made no media-repair claim.',
            'Review the scan and recover important data before further drive testing.',
            'NO PHYSICAL REPAIR',bool(attempted))
    return RepairPresentation('Repair interrupted · outcome incomplete',
        f'{evidence}. {attempts}. Do not assume the last transaction or any '
        'unvisited regions were verified.',rescue,'INCOMPLETE',True)


def drive_inspection_text(device: dict, report: dict | None = None,
                          *, error: str = '') -> str:
    """Show inventory facts even if a Windows USB IOCTL is unavailable.

    Inventory fields are advisory; suffixes (not raw serial numbers) are
    displayed. This never infers write access, recording type or disk health.
    """
    device = device or {}
    report = report if isinstance(report,dict) else {}
    def field(value):
        return str(value if value is not None else 'unknown').replace('\n',' ').replace('\r',' ')[:180]
    details = [
        'IDENTIFIED DURING DRIVE DISCOVERY (read-only)',
        f'Model: {field(device.get("model"))}',
        f'Capacity (bytes): {field(device.get("size_bytes"))}',
        f'Transport: {field(device.get("bus"))}',
        f'Serial suffix: {field(device.get("serial_suffix"))}',
        f'Logical sector size (inventory): {field(device.get("sector_size"))}',
        '',
        'OPTIONAL STORAGE-DRIVER PROBE',
    ]
    if not report:
        details += ['Unavailable. Drive discovery may still be valid, but device '
                    'capabilities and write eligibility remain unverified.']
    else:
        allowed = ('source','vendor','model','firmware_revision','bus','number',
                   'physical_sector_bytes','logical_sector_bytes','optimal_io_bytes',
                   'max_request_kib','rotational','zoned','size_bytes',
                   'reported_solid_state','protocol','smart_status','geometry_note')
        details += [f'{k.replace("_"," ").title()}: {field(report[k])}'
                    for k in allowed if report.get(k) is not None]
    if error:
        details += ['',f'Probe message: {field(error)}']
    details += ['', 'A USB bridge can hide SMART and the underlying SSD/HDD type.',
                'This window never authorizes physical writes.',
                'Read-only rescue remains an option; do not assume a failed '
                'metadata probe means the drive is healthy or damaged.']
    return '\n'.join(details)
