"""Latency-aware, media-tuned weak-region recovery planning (read-only).

Closes part of the SpinRite / OpenSuperClone gap for troubled-sector follow-up:
prioritize slow and failed offsets, adapt retry budgets by media class, and
optionally bookend a pass with SMART observations. Never authorizes patient writes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class WeakRegionBudget:
    max_reads: int
    max_elapsed_seconds: float
    max_regions: int
    statistical_samples: int
    settle_ms: int
    media_class: str
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_patient_media(device: dict | None, snapshot: dict | None = None) -> str:
    from .media_maintenance import classify_media
    return classify_media(device, snapshot)


def budget_for_media(media_class: str, *, aggressive: bool = False) -> WeakRegionBudget:
    """Bounded retry budgets — more reads are not automatically safer."""
    kind = (media_class or 'unknown').lower()
    if kind in {'ssd', 'nvme', 'flash', 'sd'}:
        # Flash benefits less from magnetic-style thrashing; keep pressure low.
        return WeakRegionBudget(
            max_reads=48 if not aggressive else 72,
            max_elapsed_seconds=45.0 if not aggressive else 60.0,
            max_regions=16,
            statistical_samples=0,
            settle_ms=0,
            media_class=kind,
            rationale='Solid-state / flash: limited rereads; prefer rescue imaging over thrashing.',
        )
    if kind in {'smr'}:
        return WeakRegionBudget(
            max_reads=64 if not aggressive else 96,
            max_elapsed_seconds=60.0 if not aggressive else 90.0,
            max_regions=16,
            statistical_samples=3 if aggressive else 0,
            settle_ms=40 if aggressive else 15,
            media_class=kind,
            rationale='SMR: conservative settle between probes; avoid adjacent-band assumptions.',
        )
    if kind in {'hdd', 'cmr', 'hdd_unknown_recording'}:
        return WeakRegionBudget(
            max_reads=96 if not aggressive else 128,
            max_elapsed_seconds=75.0 if not aggressive else 120.0,
            max_regions=24 if aggressive else 16,
            statistical_samples=3 if aggressive else 0,
            settle_ms=10 if aggressive else 0,
            media_class=kind,
            rationale='Rotational HDD: dual-read consistency first; optional statistical samples when aggressive.',
        )
    return WeakRegionBudget(
        max_reads=64,
        max_elapsed_seconds=60.0,
        max_regions=16,
        statistical_samples=0,
        settle_ms=0,
        media_class=kind or 'unknown',
        rationale='Unknown media: moderate read-only budget until classification improves.',
    )


def prioritize_ranges(ranges: list[dict], *,
                      slow_hints: list[dict] | None = None,
                      maximum: int = 32) -> list[dict]:
    """Order suspect ranges: highest observed latency first, then scan order.

    Ranges without latency stay after timed ones, preserving relative order.
    """
    if type(maximum) is not int or not 1 <= maximum <= 64:
        raise ValueError('priority maximum must be between 1 and 64')
    latency_by_offset: dict[int, float] = {}
    for hint in slow_hints or []:
        if not isinstance(hint, dict):
            continue
        off = hint.get('offset')
        lat = hint.get('latency_ms')
        if type(off) is int and isinstance(lat, (int, float)) and lat >= 0:
            previous = latency_by_offset.get(off)
            if previous is None or float(lat) > previous:
                latency_by_offset[off] = float(lat)
    ranked: list[tuple[float, int, dict]] = []
    for index, raw in enumerate(ranges):
        if not isinstance(raw, dict):
            continue
        off = raw.get('offset')
        lat = raw.get('latency_ms')
        score = -1.0
        if isinstance(lat, (int, float)) and lat >= 0:
            score = float(lat)
        elif type(off) is int and off in latency_by_offset:
            score = latency_by_offset[off]
        ranked.append((score, index, raw))
    # Higher latency first; stable for equal scores via original index.
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:maximum]]


def observe_smart_delta(before: dict | None, after: dict | None) -> dict[str, Any]:
    """Soft WATCH signals only — never a write permit or health certificate."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return {'available': False, 'changes': [], 'note': 'SMART bookend unavailable'}
    changes: list[str] = []
    for key in ('status', 'smart_status_passed', 'reported_medium'):
        if before.get(key) != after.get(key):
            changes.append(f'{key}: {before.get(key)!r} -> {after.get(key)!r}')
    before_ata = {
        x['id']: x.get('raw_value')
        for x in before.get('ata_selected_raw_attributes', [])
        if isinstance(x, dict) and type(x.get('id')) is int
    }
    after_ata = {
        x['id']: x.get('raw_value')
        for x in after.get('ata_selected_raw_attributes', [])
        if isinstance(x, dict) and type(x.get('id')) is int
    }
    for attr, label in ((5, 'reallocated'), (197, 'pending'), (198, 'offline_uncorrectable'),
                        (187, 'reported_uncorrectable'), (199, 'crc')):
        if before_ata.get(attr) != after_ata.get(attr):
            changes.append(f'ATA {attr} ({label}): {before_ata.get(attr)!r} -> {after_ata.get(attr)!r}')
    return {
        'available': True,
        'changes': changes[:12],
        'note': ('Soft WATCH only — counter movement is not proof of repair or failure.'
                 if changes else 'No selected SMART fields changed during the pass.'),
    }


def plan_weak_region_pass(device: dict | None, scan: dict | None, *,
                          snapshot: dict | None = None,
                          aggressive: bool = False) -> dict[str, Any]:
    """Decision-only plan consumed by ``recheck_errors`` and tests."""
    media = classify_patient_media(device, snapshot)
    budget = budget_for_media(media, aggressive=aggressive)
    ranges: list[dict] = []
    slow: list[dict] = []
    if isinstance(scan, dict):
        raw_ranges = scan.get('read_error_ranges')
        if isinstance(raw_ranges, list):
            ranges = [r for r in raw_ranges if isinstance(r, dict)]
        for key in ('slow_regions', 'latency_outliers', 'marginal_regions'):
            hints = scan.get(key)
            if isinstance(hints, list):
                slow.extend(h for h in hints if isinstance(h, dict))
    prioritized = prioritize_ranges(ranges, slow_hints=slow, maximum=budget.max_regions)
    return {
        'media_class': media,
        'budget': budget.as_dict(),
        'ranges_in_scan': len(ranges),
        'ranges_selected': len(prioritized),
        'prioritized_offsets': [r.get('offset') for r in prioritized[:8]],
        'patient_writes': 0,
        'summary': (f'{media.upper()}: recheck up to {budget.max_regions} regions with '
                    f'{budget.max_reads} reads / {budget.max_elapsed_seconds:.0f}s. '
                    f'{budget.rationale}'),
    }


def run_weak_region_pass(scan: dict, device: dict, reader, *,
                         snapshot: dict | None = None,
                         aggressive: bool = False,
                         health_probe: Callable[[], dict] | None = None,
                         max_reads: int | None = None,
                         max_elapsed_seconds: float | None = None) -> dict:
    """Execute a planned read-only weak-region pass with optional SMART bookends."""
    from .scan_followup import checked_ranges
    from .guided_repair import investigate_failed_ranges

    plan = plan_weak_region_pass(device, scan, snapshot=snapshot, aggressive=aggressive)
    budget = plan['budget']
    before = health_probe() if health_probe is not None else None
    # checked_ranges validates identity/geometry; then re-order by latency.
    validated = checked_ranges(scan, device, maximum=int(budget['max_regions']))
    ordered = prioritize_ranges(
        validated,
        slow_hints=(scan.get('slow_regions') if isinstance(scan.get('slow_regions'), list) else None),
        maximum=int(budget['max_regions']),
    )
    info = investigate_failed_ranges(
        reader, ordered,
        sector=int(device['sector_size']),
        max_regions=len(ordered),
        max_reads=int(max_reads if max_reads is not None else budget['max_reads']),
        max_elapsed_seconds=float(
            max_elapsed_seconds if max_elapsed_seconds is not None else budget['max_elapsed_seconds']),
        max_probe_bytes=65536,
        statistical_samples=int(budget['statistical_samples']),
        settle_ms=int(budget['settle_ms']),
    )
    after = health_probe() if health_probe is not None else None
    smart = observe_smart_delta(before if isinstance(before, dict) else None,
                                after if isinstance(after, dict) else None)
    unresolved = info['unresolved_regions']
    return {
        'status': 'read_only_weak_region_pass_completed',
        'device': {'identity_hint': device.get('identity_hint'), 'model': device.get('model')},
        'plan': plan,
        'scan_regions_considered': len(ordered),
        'original_read_failures': scan.get('read_error_chunks'),
        'repeatably_readable_ranges': info['consistent_regions'],
        'unresolved_ranges': unresolved,
        'read_calls': info['read_calls'],
        'statistical_rescues': info.get('statistical_rescues', 0),
        'remaining_unchecked': bool(info.get('budget_exhausted')) or
                               bool(scan.get('read_error_ranges_truncated')),
        'smart_observation': smart,
        'patient_writes': 0,
        'verified_files': 0,
        'message': ('Latency-prioritized reread of prior failed addresses. '
                    'No source sectors were repaired or written. '
                    'Repeatability is not a checksum of original file bytes.'),
    }
