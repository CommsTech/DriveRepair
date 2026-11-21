"""Evidence-based drive condition index, not a prediction of future survival.

Missing SMART evidence is not scored as healthy. Vendor-specific raw ATA values
are not interpreted as a universal percentage of life remaining. An optional
manufacturer rating is only used when explicitly supplied by the operator.
"""
from __future__ import annotations

from typing import Any


def _number(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def assess(snapshot: dict | None, *, scan: dict | None = None,
           manufacturer_specs: dict | None = None) -> dict:
    if not isinstance(snapshot, dict):
        return {'score': None, 'band': 'UNKNOWN', 'confidence': 'none',
                'reasons': ['SMART telemetry unavailable'], 'power_on_hours': None,
                'notes': 'No score is safer than falsely certifying a drive.'}
    _nvme_raw = snapshot.get('nvme')
    nvme = _nvme_raw if isinstance(_nvme_raw, dict) else {}
    ata = {x['id']: x.get('raw_value') for x in snapshot.get('ata_selected_raw_attributes', [])
           if isinstance(x, dict) and type(x.get('id')) is int}
    hours = _number(nvme.get('power_on_hours'))
    if hours is None:
        hours = _number(ata.get(9))
    if snapshot.get('source') == 'windows_storage_healthstatus':
        return {'score': None, 'band': 'UNKNOWN', 'confidence': 'low',
                'reasons': ['Windows HealthStatus is not a detailed SMART health baseline'],
                'power_on_hours': None, 'notes': 'Use smartctl with USB bridge support for detailed evidence.'}
    observed = []
    reasons = []
    uncalibrated_187_warning = False
    value = 100
    if snapshot.get('status') == 'failure_reported' or snapshot.get('smart_status_passed') is False:
        value -= 65
        reasons.append('Controller reports failed health')
        observed.append('controller_failure')
    elif snapshot.get('smart_status_passed') is True:
        observed.append('controller_pass')
    # ATA 187 raw values are vendor-encoded, sometimes composite bitfields.
    # Do NOT translate an arbitrary positive number into an 18-point penalty.
    specs = manufacturer_specs or {}
    raw_limits = specs.get('ata_raw_thresholds') if isinstance(specs.get('ata_raw_thresholds'), dict) else {}
    for attr, label, impact in ((5, 'Reallocated sectors', 12), (187, 'Reported uncorrectable errors', 18),
                                (197, 'Pending sectors', 24), (198, 'Offline uncorrectable', 24),
                                (199, 'Interface CRC errors / connection', 8)):
        number = _number(ata.get(attr))
        if number is not None:
            # Mark vendor attribute 187 as unscored unless an explicitly
            # supplied model-aware threshold is available.
            threshold = raw_limits.get(attr, raw_limits.get(str(attr))) if attr == 187 else 0
            verified = attr != 187 or _number(threshold) is not None
            if verified:
                observed.append(f'ata_{attr}')
            if number > 0:
                if attr == 187 and not verified:
                    uncalibrated_187_warning = True
                    reasons.append(f'{label}: {number} (raw, vendor-defined; unscored)')
                elif number > threshold:
                    value -= impact
                    reasons.append(f'{label}: {number} (raw, vendor-defined)')
    if nvme:
        critical = _number(nvme.get('critical_warning'))
        if critical is not None:
            observed.append('nvme_critical_warning')
            if critical:
                value -= 45
                reasons.append(f'NVMe critical warning bitmask: {critical}')
        errors = _number(nvme.get('media_errors'))
        if errors is not None:
            observed.append('nvme_media_errors')
            if errors:
                value -= 24
                reasons.append(f'NVMe lifetime media/data integrity errors: {errors}')
        spare = _number(nvme.get('available_spare'))
        threshold = _number(nvme.get('available_spare_threshold'))
        if spare is not None and threshold is not None:
            observed.append('nvme_spare')
            if spare <= threshold:
                value -= 25
                reasons.append(f'NVMe spare {spare}% at/below threshold {threshold}%')
        used = _number(nvme.get('percentage_used'))
        if used is not None:
            observed.append('nvme_percentage_used')
            if used >= 100:
                value -= 22
                reasons.append(f'NVMe vendor life-use estimate {used}% (not failure prediction)')
            elif used >= 80:
                value -= 10
                reasons.append(f'NVMe estimated life used: {used}%')
    if scan:
        # A failed request is neither a confirmed bad physical sector nor a proof
        # that the transport rather than the media is at fault.
        failures = _number(scan.get('read_error_chunks'))
        if failures is not None:
            observed.append('surface_probe')
            if failures:
                value -= min(30, 8 + 2 * failures)
                reasons.append(f'{failures} failed read requests (source unknown)')
    rated_hours = _number(specs.get('rated_power_on_hours'))
    if rated_hours and hours is not None:
        observed.append('documented_rated_hours')
        if hours >= rated_hours:
            reasons.append(f'Power-on hours {hours:,} meet/exceed supplied {rated_hours:,}-hour rating')
            value -= 10
    if hours is not None:
        observed.append('power_on_hours')
    # No numeric score without at least one meaningful controller health
    # verdict, wear counter or explicit surface read evidence.
    meaningful = {'controller_pass', 'controller_failure', 'surface_probe',
                  'nvme_critical_warning', 'nvme_media_errors', 'nvme_spare'}
    meaningful.update(f'ata_{x}' for x in (5, 197, 198, 199))
    if _number(raw_limits.get(187, raw_limits.get('187'))) is not None:
        meaningful.add('ata_187')
    if set(observed).issubset({'controller_pass','power_on_hours'}):
        return {'score': None, 'band': 'UNKNOWN', 'confidence': 'limited',
                'reasons': (reasons or ['SMART pass alone does not establish media reliability']),
                'power_on_hours': hours, 'notes': 'Acquire additional SMART attributes or NVMe wear counters.'}
    if not set(observed) & meaningful:
        return {'score': None, 'band': 'UNKNOWN', 'confidence': 'low',
                'reasons': (reasons or ['No comparable health or read evidence available']),
                'power_on_hours': hours,
                'notes': 'Manufacturer MTBF/AFR is fleet-level, not an individual remaining-life forecast.'}
    # A vendor-encoded uncorrectable-error counter of unknown meaning must
    # not turn into a fake 82/100 (or deceptively reassuring 100/100) badge.
    # Independently corroborated, worsening signals may still be scored.
    if uncalibrated_187_warning and value == 100:
        return {'score': None, 'band': 'UNKNOWN', 'confidence': 'limited',
                'reasons': reasons, 'power_on_hours': hours,
                'evidence_fields': sorted(set(observed)),
                'notes': ('SMART attribute 187 is vendor-encoded and has no supplied calibrated threshold. '
                          'Inspect manufacturer guidance and independent read tests; no lifespan or write authorization inferred.')}
    value = max(0, min(100, value))
    confidence = ('high' if len(observed) >= 5 and 'surface_probe' in observed else
                  'moderate' if len(observed) >= 3 else 'limited')
    band = 'CRITICAL' if value < 35 else 'AT RISK' if value < 65 else 'WATCH' if value < 85 else 'NO MAJOR SIGNALS'
    if not reasons:
        reasons.append('No major warning in the available telemetry; untested failure modes remain')
    return {'score': value, 'band': band, 'confidence': confidence,
            'reasons': reasons, 'power_on_hours': hours,
            'evidence_fields': sorted(set(observed)),
            'notes': ('Condition index is diagnostic triage, NOT likelihood of survival or manufacturer certification. '
                      'A repair does not reset wear, SMART history, or media age.')}


def compare_assessments(before: dict | None, after: dict | None) -> dict:
    a, b = assess(before), assess(after)
    delta = (b['score'] - a['score'] if a['score'] is not None and b['score'] is not None else None)
    return {'before': a, 'after': b, 'delta': delta,
            'interpretation': ('Change in observed condition indicators, not improvement in future drive lifespan. '
                               'Do not erase or discount historical error counters after a successful rewrite.')}
