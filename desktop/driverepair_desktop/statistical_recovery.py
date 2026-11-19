"""Statistical multi-sample sector recovery (public-concept maintenance ladder).

This module implements an open, fail-closed improvement on the well-known idea of
repeatedly sampling marginal magnetic media before trusting a rewrite candidate:

* settle delays between samples (mechanical/bus calm-down)
* progressive maintenance levels that raise sample count and settle time
* whole-buffer agreement first; sector-granular majority only at high confidence
* never invent bytes below the configured agreement threshold

It is **not** a reverse-engineered copy of proprietary SpinRite binaries, Flux
Synthesizer pattern generators, or patented DynaStat implementations. Techniques
are inspired by publicly documented mass-storage maintenance concepts and by
DriveRepair's own dual-read consistency rules, then tightened to refuse weak votes.

All callers that may feed a rewrite path must still pass ``advise`` /
``plan_targeted_refresh`` HDD gates. This module only reads.
"""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Mapping


ReadAt = Callable[[int, int], bytes]


@dataclass(frozen=True)
class MaintenanceLevel:
    """Intensity ladder for magnetic maintenance / investigation reads."""

    name: str
    level: int
    samples: int
    settle_ms: int
    min_agreement: float
    allow_sector_majority: bool
    description: str


# Progressive ladder. Level 1 matches classic dual identical reads.
# Higher levels add settle time and samples; sector majority is gated tightly.
MAINTENANCE_LEVELS: dict[str, MaintenanceLevel] = {
    "1": MaintenanceLevel(
        name="quick", level=1, samples=2, settle_ms=0,
        min_agreement=1.0, allow_sector_majority=False,
        description="Two identical reads; no settle (baseline consistency).",
    ),
    "2": MaintenanceLevel(
        name="normal", level=2, samples=3, settle_ms=5,
        min_agreement=1.0, allow_sector_majority=False,
        description="Three identical reads with a short settle delay.",
    ),
    "3": MaintenanceLevel(
        name="thorough", level=3, samples=5, settle_ms=15,
        min_agreement=1.0, allow_sector_majority=False,
        description="Five identical reads; longer settle for marginal media.",
    ),
    "4": MaintenanceLevel(
        name="deep", level=4, samples=8, settle_ms=25,
        min_agreement=0.75, allow_sector_majority=True,
        description="Eight samples; sector majority only at >=75% agreement.",
    ),
    "5": MaintenanceLevel(
        name="extreme", level=5, samples=15, settle_ms=40,
        min_agreement=0.80, allow_sector_majority=True,
        description="Fifteen samples; sector majority only at >=80% agreement.",
    ),
}

# Name aliases → same objects as numeric keys
MAINTENANCE_LEVELS["quick"] = MAINTENANCE_LEVELS["1"]
MAINTENANCE_LEVELS["normal"] = MAINTENANCE_LEVELS["2"]
MAINTENANCE_LEVELS["thorough"] = MAINTENANCE_LEVELS["3"]
MAINTENANCE_LEVELS["deep"] = MAINTENANCE_LEVELS["4"]
MAINTENANCE_LEVELS["extreme"] = MAINTENANCE_LEVELS["5"]


@dataclass(frozen=True)
class StatisticalReadResult:
    data: bytes
    samples_taken: int
    settle_ms: int
    method: str  # unanimous | sector_majority
    agreement_ratio: float
    sectors_majority: int
    sectors_total: int


def resolve_maintenance_level(value: str | int | None) -> MaintenanceLevel:
    """Map CLI/UI level names to a MaintenanceLevel. Default = quick/1."""
    if value is None or value == "":
        return MAINTENANCE_LEVELS["1"]
    key = str(value).strip().lower()
    level = MAINTENANCE_LEVELS.get(key)
    if level is None:
        raise ValueError(
            "maintenance level must be 1-5 or quick|normal|thorough|deep|extreme"
        )
    return level


def level_as_refresh_kwargs(level: MaintenanceLevel) -> dict:
    """Translate a maintenance level into ``refresh_media`` keyword arguments."""
    return {
        "consistency_reads": max(2, level.samples if not level.allow_sector_majority else 2),
        "statistical_samples": level.samples,
        "settle_ms": level.settle_ms,
        "min_agreement": level.min_agreement,
        "allow_sector_majority": level.allow_sector_majority,
        "maintenance_level": level.level,
        "maintenance_level_name": level.name,
    }


def _settle(settle_ms: int) -> None:
    if settle_ms > 0:
        time.sleep(min(settle_ms, 500) / 1000.0)


def _collect_samples(
    read_at: ReadAt,
    offset: int,
    length: int,
    *,
    samples: int,
    settle_ms: int,
) -> list[bytes]:
    if samples < 2:
        raise ValueError("statistical recovery requires at least 2 samples")
    if length <= 0 or offset < 0:
        raise ValueError("invalid offset/length for statistical recovery")
    collected: list[bytes] = []
    for index in range(samples):
        if index:
            _settle(settle_ms)
        blob = read_at(offset, length)
        if len(blob) != length:
            raise OSError(5, f"short read ({len(blob)} of {length})")
        collected.append(blob)
    return collected


def _unanimous(samples: list[bytes]) -> bytes | None:
    first = samples[0]
    if all(item == first for item in samples[1:]):
        return first
    return None


def _sector_majority_vote(
    samples: list[bytes],
    *,
    sector: int,
    min_agreement: float,
) -> tuple[bytes | None, int, int, float]:
    """Vote per logical sector. Fail closed on any weak sector.

    Returns (payload_or_None, majority_sectors, total_sectors, weakest_ratio).
    """
    if sector <= 0 or len(samples[0]) % sector:
        return None, 0, 0, 0.0
    length = len(samples[0])
    total = length // sector
    out = bytearray(length)
    majority_count = 0
    weakest = 1.0
    needed = max(1, int(len(samples) * min_agreement + 0.999999))  # ceil
    for sector_index in range(total):
        start = sector_index * sector
        end = start + sector
        votes = Counter(item[start:end] for item in samples)
        winner, count = votes.most_common(1)[0]
        ratio = count / len(samples)
        weakest = min(weakest, ratio)
        if count < needed or ratio < min_agreement:
            return None, majority_count, total, weakest
        out[start:end] = winner
        majority_count += 1
    return bytes(out), majority_count, total, weakest


def read_with_statistical_confidence(
    read_at: ReadAt,
    offset: int,
    length: int,
    *,
    samples: int = 3,
    settle_ms: int = 0,
    min_agreement: float = 1.0,
    allow_sector_majority: bool = False,
    sector: int = 512,
) -> StatisticalReadResult:
    """Return trusted bytes or raise RuntimeError('inconsistent_reads').

    Order of preference:
    1. Unanimous agreement across all samples (safest).
    2. Optional per-sector majority at ``min_agreement`` (deep/extreme only).
    3. Otherwise fail closed — never invent low-confidence bytes.
    """
    if not 0.5 <= min_agreement <= 1.0:
        raise ValueError("min_agreement must be between 0.5 and 1.0")
    if samples > 32:
        raise ValueError("statistical sample budget capped at 32")
    collected = _collect_samples(
        read_at, offset, length, samples=samples, settle_ms=settle_ms,
    )
    unanimous = _unanimous(collected)
    if unanimous is not None:
        return StatisticalReadResult(
            data=unanimous,
            samples_taken=len(collected),
            settle_ms=settle_ms,
            method="unanimous",
            agreement_ratio=1.0,
            sectors_majority=length // sector if sector else 0,
            sectors_total=length // sector if sector else 0,
        )
    if allow_sector_majority and min_agreement < 1.0:
        voted, maj, total, weakest = _sector_majority_vote(
            collected, sector=sector, min_agreement=min_agreement,
        )
        if voted is not None:
            return StatisticalReadResult(
                data=voted,
                samples_taken=len(collected),
                settle_ms=settle_ms,
                method="sector_majority",
                agreement_ratio=weakest,
                sectors_majority=maj,
                sectors_total=total,
            )
    raise RuntimeError("inconsistent_reads")


def summarize_level(level: MaintenanceLevel) -> Mapping[str, object]:
    return {
        "maintenance_level": level.level,
        "maintenance_level_name": level.name,
        "samples": level.samples,
        "settle_ms": level.settle_ms,
        "min_agreement": level.min_agreement,
        "allow_sector_majority": level.allow_sector_majority,
        "description": level.description,
        "not_a_spinrite_clone": True,
        "fail_closed_below_agreement": True,
    }
