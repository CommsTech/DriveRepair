"""Evidence-led physical-media decision before *any* potentially destructive operation.

This is deliberately a fail-closed decision support layer. It does not override
rolling journals, exclusive volume locks, identity checks or the scanner.
Unknown USB enclosures remain unknown. Missing SMART attributes are not a pass.
"""
from __future__ import annotations

from dataclasses import dataclass

from .health import media_from_smart, transport_from_smart
from .media_profiles import identify_profile


@dataclass(frozen=True)
class RepairAdvice:
    path: str
    label: str
    can_attempt_hdd_refresh: bool
    reasons: tuple[str, ...]
    profile: str
    confidence: str

    def public(self) -> dict:
        return {
            'path': self.path, 'label': self.label,
            'can_attempt_hdd_refresh': self.can_attempt_hdd_refresh,
            'reasons': list(self.reasons), 'profile': self.profile,
            'evidence_confidence': self.confidence,
            'notes': ('Advisory only: not a write permit, proof of correctness, '
                      'vendor-supported rejuvenation, or promise of future reliability.'),
        }


def _nvme_int(snapshot: dict, key: str) -> int | None:
    value = (snapshot.get('nvme') or {}).get(key)
    return value if type(value) is int else None


def advise(*, model: str = '', bus: str = '', media_type: str = '',
           recording: str = '', sector: int = 512,
           snapshot: dict | None = None) -> RepairAdvice:
    """Choose the least harmful path from verified media and current health.

    Logical HDD refresh is only eligible when the media type was actually
    established, not guessed from a USB bus or manufacturer model string.
    No safe blanket method exists to reconstruct physically unreadable bytes.
    """
    snap = snapshot or {}
    medium = str(snap.get('reported_medium') or media_type or '').lower()
    profile = identify_profile(model=model, bus=bus, media_type=medium,
                               recording=recording, sector=sector,
                               protocol=str(snap.get('device_protocol') or ''))
    state = media_from_smart(snapshot)
    transport = transport_from_smart(snapshot)
    reasons = []

    if state == 'FAIL' or (_nvme_int(snap, 'critical_warning') or 0):
        return RepairAdvice('rescue_replace', 'Rescue data and replace the drive', False,
                            ('Critical SMART/media warning: avoid additional patient writes.',),
                            profile.kind, 'strong_warning')
    if transport in {'WARN', 'FAIL'}:
        return RepairAdvice('stabilize_connection', 'Stabilize the cable, dock or bus; then rescue', False,
                            ('Transport errors detected; rewrites risk corrupting otherwise readable data.',),
                            profile.kind, 'transport_warning')
    temp = snap.get('temperature_c')
    if type(temp) in (int, float) and temp >= 55:
        return RepairAdvice('cool_rescue', 'Cool drive and prioritize rescue', False,
                            ('Observed temperature at or above 55 °C.',),
                            profile.kind, 'temperature_warning')
    if profile.kind in {'nvme', 'ssd', 'flash'}:
        errors = _nvme_int(snap, 'media_errors') or 0
        spare = _nvme_int(snap, 'available_spare')
        threshold = _nvme_int(snap, 'available_spare_threshold')
        used = _nvme_int(snap, 'percentage_used')
        if errors or (used is not None and used >= 100) or (
                spare is not None and threshold is not None and spare <= threshold):
            reasons.append('SSD/NVMe media-errors, spare-capacity or endurance warning: back up and replace.')
            path = 'rescue_replace'
        else:
            reasons.append('SSD/NVMe flash translation manages remapping; generic rewrite adds wear and is not an endurance repair.')
            path = 'ssd_diagnostics'
        return RepairAdvice(path, ('Image data first; use flash diagnostics' if profile.kind == 'flash'
                                   else 'Back up and use controller health/self-tests'), False,
                            tuple(reasons), profile.kind, 'device_protocol' if profile.kind == 'nvme' else profile.evidence)
    # A known model number alone does not establish the actual physical medium
    # behind a USB bridge. Require SMART rotation evidence before any HDD write.
    if profile.kind in {'smr', 'cmr', 'hdd_unknown_recording'} and medium not in {
            'hdd', 'hard disk', 'rotational'}:
        return RepairAdvice('identify_rescue', 'Verify the underlying rotational drive; image data first',
                            False, ('Recording/model labels are not proof of physical HDD media through USB.',),
                            profile.kind, 'medium_unverified')
    if profile.kind not in {'smr', 'cmr', 'hdd_unknown_recording'}:
        return RepairAdvice('identify_rescue', 'Identify media first; rescue data', False,
                            ('Underlying media cannot be verified through this device/bridge.',),
                            profile.kind, 'unknown')
    if (snap.get('source') == 'windows_native_corrob_hdd' and
            snap.get('native_hdd_corrob') is True and state == 'UNKNOWN'):
        # This is a *candidate* for the separately consented unknown-health
        # workflow, not a SMART pass or a write permit. The engine requires
        # --ack-unknown-health, exclusive access and the original-byte journal.
        return RepairAdvice('hdd_native_unknown_health',
                            'HDD identified by Windows; health unknown — explicit consent required',
                            True, ('Windows reports mechanical seek penalty and no TRIM; model, serial and size corroborate.',
                                   'The USB bridge may misreport. SMART health is UNKNOWN: rescue important data first and explicitly acknowledge unknown health.',),
                            profile.kind, 'native_corrob_not_health')
    if not snapshot or snap.get('source') == 'windows_storage_healthstatus' or state == 'UNKNOWN':
        return RepairAdvice('health_unknown', 'Obtain full SMART or corroborated native HDD identification', False,
                            ('Coarse HealthStatus is not a media-health assessment; no rotational write evidence.',),
                            profile.kind, 'insufficient')
    if state == 'WARN':
        reasons.append('HDD SMART warning: rescue important files first; risk acceptance is separately required.')
    else:
        reasons.append('No SMART media warning detected; a passed SMART snapshot does not certify the drive.')
    if profile.kind == 'smr':
        reasons.append('SMR: use small bounded, independent verified rewrites; avoid neighboring writes.')
    elif profile.kind == 'hdd_unknown_recording':
        reasons.append('Recording technology unknown: do not infer CMR or adjacent-track relationships.')
    return RepairAdvice('hdd_targeted_refresh', 'Optional journaled HDD repair after data rescue', True,
                        tuple(reasons), profile.kind, profile.evidence)
