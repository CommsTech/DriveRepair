"""Compare *available* SMART counters before/after a repair transaction.

Device error counters are evidence, not diagnostic certainty. Decreases may
reflect device resets/bridges, and reallocated-sector increases still indicate
a degrading patient even if a recent rewrite read back successfully.
"""
from __future__ import annotations

COUNTERS = {5: 'reallocated_sectors', 187: 'reported_uncorrectable',
            197: 'current_pending', 198: 'offline_uncorrectable',
            199: 'interface_crc_errors'}
NVME_COUNTERS = ('media_errors', 'num_err_log_entries', 'unsafe_shutdowns')


def _ata(snapshot):
    return {v['id']: v['raw_value'] for v in snapshot.get('ata_selected_raw_attributes', [])
            if isinstance(v, dict) and type(v.get('id')) is int and
            type(v.get('raw_value')) is int and v['id'] in COUNTERS}


def compare_health(before: dict | None, after: dict | None) -> dict:
    if not before or not after or after.get('source') == 'windows_storage_healthstatus':
        return {'status': 'unknown', 'deltas': {},
                'notes': 'Post-repair SMART counters unavailable or too coarse for a comparison.'}
    old, new = _ata(before), _ata(after)
    observed = {}
    worsening = []
    for attr, name in COUNTERS.items():
        if attr in old and attr in new:
            delta = new[attr] - old[attr]
            observed[name] = delta
            if delta > 0:
                worsening.append(f'{name} increased by {delta}')
    old_nvme = before.get('nvme') or {}
    new_nvme = after.get('nvme') or {}
    for name in NVME_COUNTERS:
        if type(old_nvme.get(name)) is int and type(new_nvme.get(name)) is int:
            delta = new_nvme[name] - old_nvme[name]
            observed[name] = delta
            if delta > 0 and name != 'unsafe_shutdowns':
                worsening.append(f'{name} increased by {delta}')
    for name in ('available_spare',):
        if type(old_nvme.get(name)) is int and type(new_nvme.get(name)) is int:
            delta = new_nvme[name] - old_nvme[name]
            observed[name] = delta
            if delta < 0:
                worsening.append(f'{name} decreased by {-delta}')
    if after.get('status') == 'failure_reported':
        worsening.append('New snapshot reports failed SMART status')
    return {
        'status': 'deteriorated' if worsening else
                  'no_new_counter_errors_observed' if observed else 'unknown',
        'deltas': observed, 'new_warnings': worsening,
        'notes': 'Counter stability does NOT prove restored reliability or prevent future failure. '
                 'A reallocated-sector increase is wear evidence, not proof of successful repair.',
    }
