"""Evidence-driven automatic investigation intensity.

Selects only read-consistency budgets; NEVER authorizes a write, overrides SMART
safety, invents bytes, or enables sector-majority reconstruction on USB media.
A higher level is more stress, not automatically better recovery.
"""
from __future__ import annotations
from dataclasses import dataclass

from .media_profiles import identify_profile


@dataclass(frozen=True)
class AutoMaintenance:
    level: int
    title: str
    explanation: str
    source: str = 'automatic evidence policy'


def choose_maintenance(*, model: str='', bus: str='', snapshot: dict | None=None,
                       read_errors: int=0, transport_errors: int=0,
                       mode: str='quick') -> AutoMaintenance:
    snap=snapshot or {}
    profile=identify_profile(model=model, bus=bus,
        media_type=str(snap.get('reported_medium') or ''),
        protocol=str(snap.get('device_protocol') or ''))
    if profile.kind not in {'hdd_unknown_recording','smr','cmr'}:
        return AutoMaintenance(1,'Identify or rescue first',
            'No HDD refresh authorized: use read-only recovery until rotational media is verified.')
    if transport_errors or str(snap.get('status') or '').lower() in {'failure_reported','smart_failed'}:
        return AutoMaintenance(1,'Minimum-stress investigation',
            'Transport or critical health warnings require rescue first; additional repetitions may increase damage.')
    if read_errors:
        return AutoMaintenance(1,'Conservative investigation',
            'Unresolved reads are isolated with bounded retries; aggressive rereading is not automatically safe.')
    if profile.kind=='smr':
        return AutoMaintenance(2,'SMR-aware conservative sampling',
            'Three matching reads and short settle; no adjacent-band rewrites or inferred track geometry.')
    if bus.lower() in {'usb','firewire','thunderbolt'}:
        return AutoMaintenance(2,'USB-aware sampling',
            'Three matching reads; avoid unnecessary retry pressure through an external controller.')
    if mode=='full' and profile.kind=='cmr':
        return AutoMaintenance(3,'Verified CMR assessment',
            'Five matching reads for full-depth investigation on a confirmed magnetic disk.')
    return AutoMaintenance(2,'Balanced HDD investigation',
        'Three matching reads with short settle; increased stress requires new evidence.')
