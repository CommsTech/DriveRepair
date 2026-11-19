"""Read-only UI eligibility hints for guided physical repairs.

The CLI/engine independently rechecks identity, SMART, mounts, journal and locks.
A model-label classification may select a *rescue* strategy but never grants a
physical-write permit. Keep this decision identical across engineering and
repair-beta UIs so a rejected operation does not briefly look like it started.
"""
from __future__ import annotations

from .repair_strategy import advise

REPAIR_OPERATIONS = frozenset({'carequick', 'carefull', 'careresume'})


def ui_repair_readiness(device: dict | None, operation: str,
                        snapshot: dict | None = None) -> tuple[bool, str]:
    if operation not in REPAIR_OPERATIONS:
        return True, ''
    if not device:
        return False, 'Select a physical drive before requesting a repair.'
    suffix = str(device.get('serial_suffix') or '').strip().lower()
    if not suffix or suffix in {'unavailable', 'unknown', 'none', 'null', 'n/a'}:
        return False, ('The USB bridge did not expose a stable device serial. '
                       'Rescue readable data to an image; for HDD repair, use a bridge '
                       'that passes identity and SMART, or connect via direct SATA.')
    if str(device.get('bus') or '').lower() not in {'usb', '1394', 'thunderbolt', 'firewire', 'sd', 'mmc'}:
        return False, 'The selected device is not an identified external whole disk.'
    if not isinstance(snapshot, dict) or not snapshot:
        return False, ('Rotational media and SMART health have not been established. '
                       'Run Diagnose → SMART health (install smartmontools if needed), '
                       'or Rescue Data now. A manufacturer model name alone is not a write permit.')
    decision = advise(model=str(device.get('model') or ''),
                      bus=str(device.get('bus') or ''),
                      sector=int(device.get('sector_size') or 512), snapshot=snapshot)
    if not decision.can_attempt_hdd_refresh:
        return False, (decision.label + '. ' + '; '.join(decision.reasons) +
                       ' Open Rescue Data to make a separate image without altering the source.')
    return True, ('Rotational HDD and SMART evidence available. The engine must still '
                  'recheck physical identity, exclusive access and a durable journal; '
                  'no repair or improved lifespan is guaranteed.')


def readiness_next_action(device: dict | None, operation: str,
                          snapshot: dict | None = None, *,
                          smartctl_available: bool = False) -> dict:
    """One deterministic next step for an otherwise blocked repair workflow.

    This is UI guidance only. Neither this decision nor a manufacturer model
    database can authorize patient writes. The CLI independently repeats its
    SMART, identity, mounted-volume, journal, and exclusive-lock checks.
    """
    eligible, reason = ui_repair_readiness(device, operation, snapshot)
    if eligible:
        return {'ready': True, 'action': 'review',
                'label': 'Review guarded repair', 'reason': reason}
    if not device:
        return {'ready': False, 'action': 'select',
                'label': 'Select a drive', 'reason': reason}
    suffix = str(device.get('serial_suffix') or '').strip().lower()
    if not suffix or suffix in {'unavailable', 'unknown', 'none', 'null', 'n/a'}:
        return {'ready': False, 'action': 'identity',
                'label': 'Review missing drive identity', 'reason': reason}
    if not snapshot or str(snapshot.get('source') or '') == 'windows_storage_healthstatus':
        if not smartctl_available:
            return {'ready': False, 'action': 'setup',
                    'label': 'Enable SMART identification',
                    'reason': (str((snapshot or {}).get('smart_unavailable_reason') or '') + ' · ' + reason).strip(' ·')}
        detail = str((snapshot or {}).get('smart_unavailable_reason') or '').strip()
        return {'ready': False, 'action': 'probe',
                'label': 'Check drive SMART and identity',
                'reason': (detail+' · '+reason) if detail else reason}
    # A completed SMART report with missing physical-media evidence is not
    # repaired by polling the same unreliable bridge indefinitely.
    return {'ready': False, 'action': 'rescue',
            'label': 'Rescue data to an image', 'reason': reason}
