"""Read-only SpinRite-class surface recovery primitives.

These are independent implementations of techniques publicly documented for
SpinRite (Steve Gibson / GRC), not a port of proprietary code:

* consensus reread with head/offset variation (majority vote across attempts)
* per-zone adaptive latency baselines for marginal-sector detection
* sector-level drilldown inside a failed chunk read

Everything here is strictly read-only. Consensus resolves *which* bytes the
drive returned most often; it is not proof those bytes are the user's original
data, and it never authorizes a rewrite. Only media_refresh may write, and only
after its own journal validation and verified read-back.
"""

from __future__ import annotations

import statistics
import time
from typing import Iterable

from .scanner import Reader

# A vote needs at least this share of covering attempts to be called consensus.
DEFAULT_MIN_AGREEMENT = 0.6


class ZoneLatencyBaselines:
    """Adaptive per-zone response-time baselines (DynaStat-style).

    Outer tracks are mechanically faster than inner tracks, so a single global
    median over-reports the inner zones as "slow" and under-reports genuine
    marginal spots. Each zone keeps its own median and MAD, and degrades to the
    global baseline until it has enough samples.
    """

    def __init__(self, zone_bytes: int = 1 << 30, min_samples: int = 8,
                 k: float = 4.0, floor_ms: float = 25.0,
                 cap_ms: float = 5000.0) -> None:
        if zone_bytes < 4096 or min_samples < 1:
            raise ValueError("Invalid zone configuration")
        self.zone_bytes = zone_bytes
        self.min_samples = min_samples
        self.k = k
        self.floor_ms = floor_ms
        self.cap_ms = cap_ms
        self._zones: dict[int, list[float]] = {}
        self._all: list[float] = []

    def observe(self, offset: int, latency_ms: float) -> None:
        if offset < 0 or latency_ms < 0:
            return
        zone = offset // self.zone_bytes
        self._zones.setdefault(zone, []).append(float(latency_ms))
        self._all.append(float(latency_ms))

    def _stats(self, samples: list[float]) -> tuple[float, float]:
        median = float(statistics.median(samples))
        if len(samples) > 1:
            mad = float(statistics.median([abs(x - median) for x in samples]))
        else:
            mad = 0.0
        threshold = median + self.k * 1.4826 * mad
        # MAD can collapse to zero on a perfectly uniform zone; never let the
        # threshold fall below a sane multiple of the local median.
        threshold = max(threshold, median * 2.0, self.floor_ms)
        return median, min(threshold, self.cap_ms)

    def baseline(self, offset: int) -> tuple[float, float] | None:
        """Return (median_ms, threshold_ms) for the zone, or global fallback."""
        zone_samples = self._zones.get(offset // self.zone_bytes)
        if zone_samples and len(zone_samples) >= self.min_samples:
            return self._stats(zone_samples)
        if self._all:
            return self._stats(self._all)
        return None

    def classify(self, offset: int, latency_ms: float) -> dict:
        base = self.baseline(offset)
        if base is None:
            return {"state": "unknown", "zone": offset // self.zone_bytes}
        median, threshold = base
        state = "marginal" if latency_ms >= threshold else "normal"
        return {
            "state": state,
            "zone": offset // self.zone_bytes,
            "median_ms": round(median, 3),
            "threshold_ms": round(threshold, 3),
            "latency_ms": round(float(latency_ms), 3),
            "ratio": round(float(latency_ms) / median, 3) if median > 0 else None,
        }


def _vote(blocks: list[bytes | None], length: int) -> tuple[bytes | None, float, int]:
    """Position-wise plurality vote across aligned attempts.

    Returns (consensus_bytes, agreement, covered_positions). ``agreement`` is
    the mean share of covering attempts backing the winning value at each
    voted position, so a 2-of-3 split scores 0.667 for those bytes.
    """
    out = bytearray()
    covered = 0
    score = 0.0
    for index in range(length):
        tally: dict[int, int] = {}
        for block in blocks:
            if block is not None and index < len(block):
                value = block[index]
                tally[value] = tally.get(value, 0) + 1
        if not tally:
            continue
        winner, count = max(tally.items(), key=lambda item: (item[1], -item[0]))
        total = sum(tally.values())
        out.append(winner)
        covered += 1
        score += count / total
    if not covered:
        return None, 0.0, 0
    return bytes(out), score / covered, covered


def consensus_read(reader: Reader, offset: int, length: int, *,
                   sector: int = 512, attempts: int = 3,
                   shifts: Iterable[int] = (-1, 0, 1),
                   min_agreement: float = DEFAULT_MIN_AGREEMENT,
                   deadline: float | None = None) -> dict:
    """Re-read a region with varying read starts and vote on the result.

    Marginal sectors often return different bytes depending on exact head
    position, so a shifted reread can succeed where the aligned one fails.
    This never writes and never claims the winning bytes are correct.
    """
    if length <= 0 or sector <= 0 or attempts < 1:
        raise ValueError("Invalid consensus parameters")
    length = length - (length % sector) or sector
    shift_list = [int(s) for s in shifts][:max(1, attempts)]
    if not shift_list:
        shift_list = [0]
    pad = max((abs(s) for s in shift_list), default=0) * sector
    started = time.monotonic()
    blocks: list[bytes | None] = []
    errors: list[str] = []
    successful = 0
    for index in range(attempts):
        if deadline is not None and time.monotonic() >= deadline:
            break
        shift = shift_list[index % len(shift_list)]
        start = offset - pad + shift * sector
        if start < 0:
            start = 0
        want = length + (offset - start) + pad
        try:
            raw = reader.read_at(start, want)
        except OSError as exc:
            errors.append(f"{type(exc).__name__}")
            blocks.append(None)
            continue
        successful += 1
        slice_start = offset - start
        chunk = raw[slice_start:slice_start + length]
        blocks.append(chunk if len(chunk) == length else None)
    data, agreement, covered = _vote(blocks, length)
    if successful == 0:
        status = "all_failed"
    elif data is None:
        status = "no_data"
    elif agreement >= min_agreement and covered == length:
        status = "consensus"
    else:
        status = "no_consensus"
    return {
        "status": status,
        "offset": offset,
        "length": length,
        "attempts": len(blocks),
        "successful_reads": successful,
        "agreeing_bytes_pct": round(agreement * 100, 3),
        "covered_bytes": covered,
        "distinct_blocks": len({b for b in blocks if b is not None}),
        "data": data if status == "consensus" else None,
        "errors": errors,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "interpretation": ("Majority of shifted rereads agree; bytes still UNVERIFIED "
                           "against any filesystem checksum."),
    }


def sector_drilldown(reader: Reader, offset: int, length: int, *,
                     sector: int = 512, max_sectors: int = 256,
                     max_elapsed_seconds: float = 8.0,
                     progress=None) -> dict:
    """Probe individual sectors inside a failed chunk, bounded.

    A failed 1 MiB read identifies an unknown 1 MiB range; probing sectors
    narrows where reads actually fail without assuming 512-byte granularity is
    physical.
    """
    if length <= 0 or sector <= 0 or max_sectors < 1:
        raise ValueError("Invalid drilldown parameters")
    total = max(1, length // sector)
    count = min(total, max_sectors)
    if count == 1:
        indices = [0]
    else:
        step = (total - 1) / (count - 1)
        indices = sorted({int(round(i * step)) for i in range(count)})
    started = time.monotonic()
    deadline = started + max_elapsed_seconds
    failed: list[dict] = []
    slow: list[dict] = []
    latencies: list[float] = []
    probed = 0
    for index in indices:
        if time.monotonic() >= deadline:
            break
        position = offset + index * sector
        t0 = time.monotonic()
        try:
            data = reader.read_at(position, sector)
            elapsed = (time.monotonic() - t0) * 1000
            probed += 1
            if len(data) != sector:
                failed.append({"offset": position, "error": "short_read"})
            else:
                latencies.append(elapsed)
                slow.append({"offset": position, "latency_ms": round(elapsed, 3)})
        except OSError as exc:
            probed += 1
            failed.append({"offset": position, "error": type(exc).__name__})
        if progress:
            try:
                progress(probed, len(indices))
            except TypeError:
                progress(probed, len(indices))
    median = statistics.median(latencies) if latencies else None
    threshold = max(50.0, median * 4) if median is not None else None
    slow_sectors = [item for item in slow
                    if threshold is not None and item["latency_ms"] >= threshold]
    return {
        "offset": offset,
        "length": length,
        "sector_bytes": sector,
        "sectors_in_range": total,
        "sectors_probed": probed,
        "failed_sectors": failed[:max_sectors],
        "failed_sector_count": len(failed),
        "slow_sectors": slow_sectors[:max_sectors],
        "slow_sector_count": len(slow_sectors),
        "median_ms": None if median is None else round(median, 3),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "interpretation": ("Sector probes locate failing LOGICAL sectors; they do not "
                           "prove physical media damage or authorize a rewrite."),
    }
