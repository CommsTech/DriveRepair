"""Conservative plan for scan-driven, explicitly approved sector refresh.

This *does not* reconstruct corrupt file bytes. A slow but consistently readable
region may benefit from rerecording, but an I/O error, unstable bytes, or failing
SMART counter means STOP and image/rescue first. Only the journaled engine writes.
"""
from __future__ import annotations

import math

from .health import media_from_smart, transport_from_smart


def tuned_scan(*, size: int, sector: int, mode: str, bus: str = "") -> dict:
    """Deterministic bounded-memory defaults; performance claims need hardware tests."""
    if mode not in {"quick", "full"} or size <= 0 or sector <= 0:
        raise ValueError("Invalid assisted scan request")
    # Large disks need larger sequential reads, not millions of progress events.
    chunk = 4 * 1024 * 1024 if mode == "full" and size >= 512 * 1024**3 else 1024 * 1024
    chunk = max(sector, (chunk + sector - 1) // sector * sector)
    samples = 256 if size >= 1024**4 else 128
    if mode == "quick" and bus.lower() in {"usb", "7", "12", "firewire"}:
        samples = min(samples, 128)  # avoid exhausting marginal USB docks
    return {"mode": "triage" if mode == "quick" else "full",
            "chunk": chunk, "samples": samples, "max_errors": 16}


def plan_targeted_refresh(scan: dict, *, sector: int, chunk: int,
                          max_regions: int = 64, smart: dict | None = None,
                          hardware: bool = False, allow_unknown_health: bool = False) -> dict:
    """Return a bounded candidate set or a fail-closed explanation. Never a write permit."""
    reasons: list[str] = []
    if scan.get("status") not in {"completed", "completed_with_slow_regions"}:
        reasons.append("Scan was incomplete or encountered errors; rescue data before rewriting")
    if int(scan.get("read_error_chunks") or 0) or scan.get("inconsistent_reads") or scan.get("repeat_probe_failures"):
        reasons.append("Unreadable or inconsistent source data; a rewrite could erase it")
    if scan.get("mode") not in {"triage", "full"}:
        reasons.append("Assisted repair requires triage or full scan")
    if scan.get('slow_regions_truncated'):
        reasons.append('Slow-region list truncated; refuse a partial silent repair')
    if not 1 <= max_regions <= 256:
        raise ValueError("Region budget must be 1–256")
    if hardware:
        medium = media_from_smart(smart)
        transport = transport_from_smart(smart)
        if medium in {"FAIL", "WARN"} or transport == "WARN":
            reasons.append("Drive/transport health warning; stabilize and rescue first")
        # Windows coarse health without SMART attributes is not evidence of a
        # healthy disk, particularly through an external USB bridge.
        if smart and smart.get("source") == "windows_storage_healthstatus":
            medium = "UNKNOWN"
        if medium == "UNKNOWN" and not allow_unknown_health:
            reasons.append("SMART health unavailable; requires separate unknown-health acknowledgment")
        if smart:
            temp = smart.get("temperature_c")
            if type(temp) in {int, float} and temp >= 55:
                reasons.append("Drive temperature is high; cool/stabilize before write maintenance")
            nvme = smart.get("nvme") or {}
            if type(nvme.get("percentage_used")) is int and nvme["percentage_used"] >= 100:
                reasons.append("NVMe reported endurance exhausted; replace instead of refreshing")
    if reasons:
        return {"status": "blocked", "reasons": reasons, "targets": [], "candidate_count": 0}
    size = int(scan["device_size_bytes"])
    regions = []
    for raw in scan.get("slow_regions") or []:
        off = raw.get("offset")
        if type(off) is not int or off < 0 or off >= size or off % sector:
            continue
        length = min(chunk, size - off)
        length -= length % sector
        if not length:
            continue
        if raw.get("latency_ms") is None or not math.isfinite(float(raw["latency_ms"])):
            continue
        # Never guess the exact bad sector from coarse read latency.
        regions.append((off, length))
    regions = sorted(set(regions))
    if any(a[0] + a[1] > b[0] for a, b in zip(regions, regions[1:])):
        return {"status": "blocked", "reasons": ["Overlapping suspect regions"],
                "targets": [], "candidate_count": len(regions)}
    if len(regions) > max_regions:
        return {"status": "blocked", "reasons": ["Too many suspect regions for safe bounded maintenance"],
                "targets": [], "candidate_count": len(regions)}
    return {
        "status": "candidates_found" if regions else "no_candidates",
        "reasons": [], "targets": regions, "candidate_count": len(regions),
        "notes": ("Candidate offsets are from latency anomalies, not verified bit errors. "
                  "The write engine must reread the original bytes consistently, "
                  "save them outside the source, rewrite, then verify. "
                  "A clean scan is NOT a checksum or health certification."),
    }
