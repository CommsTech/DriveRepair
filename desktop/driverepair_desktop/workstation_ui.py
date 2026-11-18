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
        'Rescue data',
        'Save readable data onto another healthy disk before attempting invasive work.',
        'Read-only source', 'Writes only to a new destination image',
        'Select your external source drive. A destination image is chosen when you start.'),
    'fix': Workspace(
        'Repair weak regions',
        'Experimental media rewrites never reconstruct data that cannot be read consistently.',
        'Experimental writes', 'May permanently worsen a failing drive',
        'Use recovery first. Review the write risks and durable-journal options.'),
}

IMAGE_OPERATIONS = frozenset({'rescueimage'})
EXPERIMENTAL_OPERATIONS = frozenset({'carequick', 'carefull', 'careresume'})


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
    if kind in EXPERIMENTAL_OPERATIONS:
        return True, 'Ready for required safety review, fingerprint confirmation and journaling.'
    return True, 'Ready to start read-only diagnostics.'


def operation_impact(kind: str | None) -> tuple[str, str]:
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
        f'Read errors / unresolved data: {errors}',
        f'Measured successful read coverage: {observed_coverage}',
        'Interpretation: completed operations and readable regions do not certify file integrity or media lifespan.',
    ))
