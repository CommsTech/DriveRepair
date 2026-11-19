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
