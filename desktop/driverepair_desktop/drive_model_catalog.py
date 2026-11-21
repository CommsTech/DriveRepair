"""Curated, offline, source-attributed storage model catalog.

Vendor specifications guide read strategies, not patient write permissions. No
network lookups, untrusted automatic updates, or guesses from adjacent models.
"""
from __future__ import annotations

from functools import lru_cache
from importlib import resources
import json
import re


@lru_cache(maxsize=1)
def catalog_entries() -> tuple[dict, ...]:
    payload = json.loads(resources.files('driverepair_desktop').joinpath('data/drive_models.json').read_text(encoding='utf-8'))
    if payload.get('schema_version') != 1 or not isinstance(payload.get('models'), list):
        raise ValueError('Unsupported or corrupt DriveRepair drive model catalog')
    entries = []
    seen = set()
    for record in payload['models']:
        model = record.get('model')
        mode = record.get('match')
        if (not isinstance(model, str) or not re.fullmatch(r'[A-Z0-9-]{4,64}', model)
                or mode not in {'exact', 'family_prefix'}
                or record.get('medium') not in {'hdd', 'ssd', 'nvme', 'flash'}
                or record.get('recording') not in {None, 'smr', 'cmr'}
                or not isinstance(record.get('source_url'), str)
                or not record['source_url'].startswith('https://')):
            raise ValueError('Invalid or unattributed drive model catalog record')
        key = (model, mode)
        if key in seen:
            raise ValueError('Duplicate model catalog entry')
        seen.add(key)
        entries.append(record)
    return tuple(entries)


def published_model_guidance(model_name: str) -> dict | None:
    """Return sourced manufacturer specifications, NOT a life-expectancy guess.

    Many manufacturers publish workload or endurance ratings, not a maximum
    power-on-hour lifetime. Missing service-hour specifications stay unknown.
    """
    matches = match_catalog_models(model_name)
    if len(matches) != 1:
        return None
    row = matches[0]
    return {
        'manufacturer': row['manufacturer'], 'model': row['model'],
        'source_url': row['source_url'],
        'rated_power_on_hours': row.get('rated_power_on_hours'),
        'workload_tb_per_year_max_exclusive': row.get('workload_tb_per_year_max_exclusive'),
        'endurance_tbw': row.get('endurance_tbw'),
    }


def match_catalog_models(model_name: str) -> tuple[dict, ...]:
    """Match complete OEM model tokens, allowing a vendor prefix and suffix.

    A family match is an advisory storage category, not a serial attestation.
    The library does not infer the medium of a different model from a prefix.
    """
    raw = model_name.upper().strip()
    normalized = re.sub(r'(?<=[A-Z0-9])\s+(?=[0-9])', '', raw)
    matches = []
    for row in catalog_entries():
        part = re.escape(row['model'])
        if row['match'] == 'exact':
            pattern = rf'(?<![A-Z0-9]){part}(?![A-Z0-9])'
        else:
            pattern = rf'(?<![A-Z0-9]){part}(?=[-\s]|$)'
        if re.search(pattern, normalized if row['match'] == 'exact' else raw):
            matches.append(row)
    return tuple(matches)
