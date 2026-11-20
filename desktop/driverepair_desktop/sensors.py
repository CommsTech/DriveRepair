"""Optional chassis sensors correlated with I/O offsets.

Acoustic WATCH and IMU shock are *non-authoritative* soft signals. They never
prove platter wear. Room microphones and laptop gyros are noisy; contact mics
and shock gates are the intended use. Latency/SMART remain primary.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SensorEvent:
    kind: str  # acoustic_watch | shock_guard | smart_delta
    severity: str  # info | watch | stop
    message: str
    offset_bytes: int | None = None
    monotonic_s: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class AcousticWatcher:
    """Optional broadband energy sampler; marks WATCH when energy spikes.

    Without a capture backend the watcher stays unavailable (not FAIL).
    """

    def __init__(self, *, threshold_db: float = 12.0, sample_hz: int = 8):
        self.threshold_db = threshold_db
        self.sample_hz = sample_hz
        self.baseline: float | None = None
        self.available = False
        self._backend: Any = None
        self._last = 0.0
        self._init_backend()

    def _init_backend(self) -> None:
        try:
            import sounddevice as sd  # type: ignore
            self._backend = sd
            self.available = True
        except Exception:
            self.available = False
            self._backend = None

    def poll(self, *, offset_bytes: int | None = None) -> SensorEvent | None:
        now = time.monotonic()
        if not self.available or now - self._last < (1.0 / max(1, self.sample_hz)):
            return None
        self._last = now
        try:
            # Short mono burst (~50 ms). Not calibrated SPL — relative only.
            duration = 0.05
            rate = 16000
            frames = int(rate * duration)
            recording = self._backend.rec(frames, samplerate=rate, channels=1, dtype="float32")
            self._backend.wait()
            samples = recording.reshape(-1)
            rms = math.sqrt(float((samples * samples).mean()) + 1e-12)
            db = 20.0 * math.log10(rms + 1e-12)
        except Exception as exc:
            self.available = False
            return SensorEvent(
                kind="acoustic_watch", severity="info",
                message=f"Acoustic capture unavailable ({type(exc).__name__})",
                offset_bytes=offset_bytes, monotonic_s=now,
            )
        if self.baseline is None:
            self.baseline = db
            return SensorEvent(
                kind="acoustic_watch", severity="info",
                message=f"Acoustic baseline set ({db:.1f} dBFS rel)",
                offset_bytes=offset_bytes, monotonic_s=now,
                details={"db": db, "baseline": self.baseline},
            )
        delta = db - self.baseline
        # Slow baseline drift so speech doesn't permanently raise threshold.
        self.baseline = (0.98 * self.baseline) + (0.02 * db)
        if delta >= self.threshold_db:
            return SensorEvent(
                kind="acoustic_watch", severity="watch",
                message=f"Acoustic energy +{delta:.1f} dB over baseline near I/O",
                offset_bytes=offset_bytes, monotonic_s=now,
                details={"db": db, "delta_db": delta, "baseline": self.baseline},
            )
        return None


class ShockGuard:
    """Optional IMU / accelerometer shock interlock (chassis motion, not platter wobble)."""

    def __init__(self, *, threshold_g: float = 1.5):
        self.threshold_g = threshold_g
        self.available = False
        self._reader: Callable[[], float] | None = None
        self._init_backend()

    def _init_backend(self) -> None:
        # Prefer an injected reader in tests; otherwise try a Windows sensor probe.
        try:
            # Optional winrt accelerometer — may be absent on desktops.
            from winrt.windows.devices.sensors import Accelerometer  # type: ignore
            sensor = Accelerometer.get_default()
            if sensor is None:
                return

            def _read() -> float:
                reading = sensor.get_current_reading()
                if reading is None:
                    return 0.0
                ax, ay, az = reading.acceleration_x, reading.acceleration_y, reading.acceleration_z
                # Magnitude in g (WinRT already reports g).
                return math.sqrt(ax * ax + ay * ay + az * az)

            self._reader = _read
            self.available = True
        except Exception:
            self.available = False
            self._reader = None

    def set_reader(self, reader: Callable[[], float] | None) -> None:
        self._reader = reader
        self.available = reader is not None

    def poll(self, *, offset_bytes: int | None = None) -> SensorEvent | None:
        if not self.available or self._reader is None:
            return None
        try:
            g = float(self._reader())
        except Exception as exc:
            self.available = False
            return SensorEvent(
                kind="shock_guard", severity="info",
                message=f"IMU unavailable ({type(exc).__name__})",
                offset_bytes=offset_bytes, monotonic_s=time.monotonic(),
            )
        if g >= self.threshold_g:
            return SensorEvent(
                kind="shock_guard", severity="stop",
                message=f"Chassis shock {g:.2f} g >= {self.threshold_g:.2f} g; pause destructive I/O",
                offset_bytes=offset_bytes, monotonic_s=time.monotonic(),
                details={"g": g, "threshold_g": self.threshold_g},
            )
        return None


class SmartDeltaTracker:
    """Compare selected SMART counters; rising realloc/pending/CRC => WATCH."""

    INTERESTING = {
        "ata.5", "ata.187", "ata.197", "ata.198",
        "nvme.media_errors", "nvme.num_err_log_entries", "nvme.critical_warning",
    }

    def __init__(self):
        self.baseline: dict[str, int] | None = None

    def ingest(self, counters: dict[str, int], *, offset_bytes: int | None = None) -> list[SensorEvent]:
        events: list[SensorEvent] = []
        filtered = {k: v for k, v in counters.items() if k in self.INTERESTING and type(v) is int}
        if self.baseline is None:
            self.baseline = dict(filtered)
            events.append(SensorEvent(
                kind="smart_delta", severity="info",
                message="SMART delta baseline recorded",
                offset_bytes=offset_bytes, monotonic_s=time.monotonic(),
                details={"baseline": dict(filtered)},
            ))
            return events
        for key, value in filtered.items():
            prev = self.baseline.get(key)
            if prev is not None and value > prev:
                events.append(SensorEvent(
                    kind="smart_delta", severity="watch",
                    message=f"SMART {key} increased ({prev} -> {value})",
                    offset_bytes=offset_bytes, monotonic_s=time.monotonic(),
                    details={"key": key, "before": prev, "after": value},
                ))
                self.baseline[key] = value
            elif prev is None:
                self.baseline[key] = value
        return events


class SensorSuite:
    """Bundles optional sensors and correlates events with the active I/O offset."""

    def __init__(self, *, acoustic: bool = False, shock: bool = False, smart_deltas: bool = False):
        self.acoustic = AcousticWatcher() if acoustic else None
        self.shock = ShockGuard() if shock else None
        self.smart = SmartDeltaTracker() if smart_deltas else None
        self.events: list[SensorEvent] = []
        self.last_offset: int | None = None

    def note_offset(self, offset_bytes: int | None) -> None:
        self.last_offset = offset_bytes

    def poll(self, *, offset_bytes: int | None = None) -> list[SensorEvent]:
        off = offset_bytes if offset_bytes is not None else self.last_offset
        found: list[SensorEvent] = []
        if self.acoustic:
            ev = self.acoustic.poll(offset_bytes=off)
            if ev:
                found.append(ev)
        if self.shock:
            ev = self.shock.poll(offset_bytes=off)
            if ev:
                found.append(ev)
        self.events.extend(found)
        return found

    def ingest_smart_counters(self, counters: dict[str, int], *,
                              offset_bytes: int | None = None) -> list[SensorEvent]:
        if not self.smart:
            return []
        off = offset_bytes if offset_bytes is not None else self.last_offset
        found = self.smart.ingest(counters, offset_bytes=off)
        self.events.extend(found)
        return found

    def should_stop(self) -> bool:
        return any(e.severity == "stop" for e in self.events)

    def public_summary(self) -> dict[str, Any]:
        return {
            "acoustic_available": bool(self.acoustic and self.acoustic.available),
            "shock_available": bool(self.shock and self.shock.available),
            "smart_deltas_enabled": self.smart is not None,
            "events": [
                {
                    "kind": e.kind,
                    "severity": e.severity,
                    "message": e.message,
                    "offset_bytes": e.offset_bytes,
                    "details": e.details,
                }
                for e in self.events[-64:]
            ],
            "notes": (
                "Acoustic/IMU signals are soft indicators only. They do not measure "
                "platter flying height or bearing play. Prefer latency maps and SMART."
            ),
        }
