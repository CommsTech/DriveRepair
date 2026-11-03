"""Evidence-scoped media profiles for DriveRepair.

A USB bridge is a transport, NOT a recording technology. Unknown media stays
unknown. Profiles tune *reads*; no profile is itself a write authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

MIB = 1024 * 1024

# Manufacturer datasheet, BarraCuda 2.5 DS1907: ST1000LM048 = SMR.
# Never extrapolate model families to all Seagate drives.
KNOWN_SMR_MODELS = frozenset({'ST1000LM048', 'ST500LM030', 'ST500LM034'})


@dataclass(frozen=True)
class MediaProfile:
    kind: str
    evidence: str
    quick_chunk: int
    full_start_chunk: int
    full_max_chunk: int
    read_min_chunk: int
    quick_fraction: float = 0.10
    neighbor_rewrite: bool = False
    maintenance_note: str = ''


def identify_profile(*, model: str = '', bus: str = '', media_type: str = '',
                     recording: str = '', sector: int = 512) -> MediaProfile:
    """Prefer confirmed recording data, then exact model evidence; never guess CMR.

    media_type may be supplied from a reliable OS storage-property query; it is
    not inferred from the word 'USB'. recording must be verified independently.
    """
    if sector <= 0 or sector & (sector - 1):
        raise ValueError('Invalid logical sector size')
    # Match only a complete OEM part number (possibly after a vendor prefix),
    # never a model family or an arbitrary longer suffix. Whitespace within a
    # printed part number is tolerated, but firmware suffixes need boundaries.
    model_id = re.sub(r'(?<=[A-Z0-9])\s+(?=[0-9])', '', model.upper().strip())
    known_smr = any(re.search(rf'(?<![A-Z0-9]){part}(?![A-Z0-9])', model_id)
                    for part in KNOWN_SMR_MODELS)
    bus_id = bus.strip().lower()
    recording_id = recording.strip().lower()
    medium = media_type.strip().lower()
    if recording_id not in {'', 'smr', 'cmr'}:
        raise ValueError('Unknown recording technology')
    if recording_id == 'smr' or (not recording_id and known_smr):
        kind, evidence = 'smr', ('confirmed recording' if recording_id else 'manufacturer model datasheet')
    elif recording_id == 'cmr':
        kind, evidence = 'cmr', 'confirmed recording'
    elif bus_id in {'nvme', 'nvm express'}:
        kind, evidence = 'nvme', 'NVMe protocol'
    elif medium in {'ssd', 'solid state', 'solid-state'}:
        kind, evidence = 'ssd', 'reported solid-state medium'
    elif medium in {'hdd', 'hard disk', 'rotational'}:
        kind, evidence = 'hdd_unknown_recording', 'reported rotational medium; recording unspecified'
    else:
        kind, evidence = 'unknown', 'no authoritative medium/recording identification'
    # Large, aligned sequential requests for good regions, bounded follow-up
    # reads for problem areas. Device/adapter max-transfer limits can be lower.
    specs = {
        'smr': (16, 4, 16, 256, 'Avoid adjacent random writes; firmware may rewrite entire shingled bands.'),
        'cmr': (16, 4, 16, 256, 'Qualify every neighbor independently before any authorized write.'),
        'hdd_unknown_recording': (8, 2, 8, 256, 'Do not assume CMR or write adjacent blocks.'),
        'ssd': (16, 4, 16, 128, 'Avoid unnecessary refresh writes, which consume flash endurance.'),
        'nvme': (16, 4, 16, 128, 'Prefer health logs and controller-level maintenance; avoid write amplification.'),
        'unknown': (8, 1, 8, 256, 'Identify underlying media before choosing write-intensive maintenance.'),
    }
    quick, initial, maximum, minimum_kib, note = specs[kind]
    def aligned(n):
        return max(sector, (n // sector) * sector)
    return MediaProfile(kind, evidence, aligned(quick * MIB), aligned(initial * MIB),
                        aligned(maximum * MIB), aligned(minimum_kib * 1024),
                        maintenance_note=note)


def quick_coverage_plan(size: int, chunk: int, *, fraction: float = 0.10) -> dict:
    """Plan >= fraction of unique addresses without keeping a block-sized array."""
    if size <= 0 or chunk <= 0 or not 0 < fraction <= 1:
        raise ValueError('Invalid coverage plan')
    blocks = (size + chunk - 1) // chunk
    # For the tail, a ceiling on block count alone might not reach 10%.
    selected = min(blocks, max(1, __import__('math').ceil((size * fraction) / chunk) + 1))
    return {'samples': selected, 'requested_coverage_pct': fraction * 100,
            'planned_min_bytes': int(size * fraction), 'chunk': chunk,
            'estimated_min_read_seconds_at_120_mib_s': size * fraction / (120*MIB)}


def format_quick_preflight(size: int | None, chunk: int = MIB, *, fraction: float = 0.10) -> str:
    """Operator-facing preflight text. Never promises duration or drive health."""
    if not size or size <= 0:
        return ('Quick surface check: capacity unknown — planned coverage cannot be estimated. '
                'Any time shown later is observed throughput, not a promise.')
    plan = quick_coverage_plan(size, chunk, fraction=fraction)
    planned = plan['planned_min_bytes']
    seconds = plan['estimated_min_read_seconds_at_120_mib_s']
    if planned >= MIB:
        planned_txt = f'{planned / MIB:.1f} MiB'
    else:
        planned_txt = f'{planned} bytes'
    return (
        f'Quick surface check plans about {plan["requested_coverage_pct"]:.0f}% '
        f'({planned_txt}, {plan["samples"]} samples). '
        f'At an assumed 120 MiB/s this is roughly {seconds:.0f}s of reading — '
        'not a duration guarantee and not a health certificate.'
    )
