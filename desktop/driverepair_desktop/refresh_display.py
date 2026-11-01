"""Live console dashboard for In-Place Media Refresh.

Stdlib-only ANSI/ASCII UI so long adaptive probes do not look stalled.
Acoustic sensors are not available over USB; mechanical risk is inferred from
latency spikes, variance, and I/O error patterns.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field


def _bar(done: int, total: int, width: int = 28) -> str:
    total = max(1, total)
    filled = min(width, int(width * done / total))
    return "#" * filled + "." * (width - filled)


def _fmt_bytes(n: int) -> str:
    for unit, size in (("TiB", 1024**4), ("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024)):
        if n >= size:
            return f"{n / size:.2f} {unit}"
    return f"{n} B"


def _fmt_secs(seconds: float | None) -> str:
    if seconds is None:
        return "--"
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    return f"{minutes}m{int(seconds % 60):02d}s"


@dataclass
class HealthIndicators:
    media: str = "OK"          # OK | WARN | FAIL
    transport: str = "OK"      # OK | WARN | FAIL
    mechanical: str = "OK"     # OK | WATCH | FAIL  (latency/variance proxy; not a microphone)


@dataclass
class RefreshDashboard:
    mode: str
    size: int
    enabled: bool = True
    stream: object = field(default_factory=lambda: sys.stderr)
    phase: str = "starting"
    probe_done: int = 0
    probe_total: int = 0
    refresh_done: int = 0
    refresh_total: int = 0
    rewritten: int = 0
    verified: int = 0
    offset: int = 0
    latency_s: float | None = None
    median_s: float | None = None
    threshold_s: float | None = None
    journal_backend: str = "disk"
    health: HealthIndicators = field(default_factory=HealthIndicators)
    map_cells: list[str] = field(default_factory=list)
    map_width: int = 40
    message: str = ""
    started: float = field(default_factory=time.monotonic)
    _last_draw: float = 0.0
    anomalies: list[str] = field(default_factory=list)

    def ensure_map(self) -> None:
        if len(self.map_cells) != self.map_width:
            self.map_cells = ["."] * self.map_width

    def mark_map(self, offset: int, symbol: str) -> None:
        self.ensure_map()
        if self.size <= 0:
            return
        idx = min(self.map_width - 1, int(offset * self.map_width / self.size))
        # Prefer error/slow markers over plain OK. ASCII-only for Windows consoles.
        rank = {".": 0, "o": 1, "S": 2, "!": 3, "X": 4}
        if rank.get(symbol, 0) >= rank.get(self.map_cells[idx], 0):
            self.map_cells[idx] = symbol

    def note_anomaly(self, text: str) -> None:
        if text not in self.anomalies:
            self.anomalies.append(text)
            if len(self.anomalies) > 6:
                self.anomalies = self.anomalies[-6:]

    def update_health_from_event(self, event: dict) -> None:
        kind = event.get("error_class")
        latency = event.get("latency_s")
        if kind in {"transport_or_disconnect", "timeout"}:
            self.health.transport = "FAIL"
            self.note_anomaly(f"Transport/timeout at offset {event.get('offset', 0):,}")
        elif kind in {"media_or_io", "os_error"}:
            self.health.media = "FAIL" if kind == "media_or_io" else "WARN"
            self.note_anomaly(f"Media/I/O issue at offset {event.get('offset', 0):,}")
        if latency is not None and self.threshold_s and latency >= max(self.threshold_s * 3, 0.25):
            self.health.mechanical = "WATCH" if self.health.mechanical == "OK" else self.health.mechanical
            self.note_anomaly(f"High latency {_fmt_secs(latency)} (mechanical/USB proxy)")
        if event.get("mechanical_fail"):
            self.health.mechanical = "FAIL"
            self.note_anomaly("Mechanical-suspect pattern: repeated extreme latency / seek thrash")

    def handle(self, event: dict) -> None:
        if not self.enabled:
            return
        status = event.get("status") or event.get("phase") or self.phase
        if status == "probing" or event.get("phase") == "probe":
            self.phase = "PROBE"
            self.probe_done = int(event.get("probe_index", self.probe_done))
            self.probe_total = int(event.get("probe_total", self.probe_total))
            self.offset = int(event.get("offset", self.offset))
            self.latency_s = event.get("latency_s", self.latency_s)
            self.median_s = event.get("median_s", self.median_s)
            self.threshold_s = event.get("threshold_s", self.threshold_s)
            symbol = "o"
            if event.get("failed"):
                symbol = "X"
            elif self.threshold_s and self.latency_s and self.latency_s >= self.threshold_s:
                symbol = "S"
            self.mark_map(self.offset, symbol)
            self.message = event.get("message") or f"Probing sample {self.probe_done}/{self.probe_total}"
        elif status in {"in_progress", "refreshing"} or event.get("phase") == "refresh":
            self.phase = "REFRESH"
            self.refresh_done = int(event.get("refresh_index", self.refresh_done))
            self.refresh_total = int(event.get("refresh_total", self.refresh_total))
            self.rewritten = int(event.get("rewritten_bytes", self.rewritten))
            self.verified = int(event.get("verified_bytes", self.verified))
            self.offset = int(event.get("offset", self.offset))
            self.message = event.get("message") or f"Refreshing region @ {self.offset:,}"
            self.mark_map(self.offset, "S")
        elif status == "escalating" or event.get("phase") == "escalate":
            self.phase = "ESCALATE"
            self.message = event.get("message") or "Auto-escalating deeper test on suspect region"
            self.mark_map(int(event.get("offset", self.offset)), "!")
        if event.get("error_class") or event.get("mechanical_fail") or event.get("latency_s"):
            self.update_health_from_event(event)
        # Redraw at least ~8 Hz, always on phase changes / errors.
        now = time.monotonic()
        force = bool(event.get("force") or event.get("failed") or event.get("mechanical_fail"))
        if force or now - self._last_draw >= 0.12 or status in {"probing", "starting"}:
            self.draw()
            self._last_draw = now

    def _is_tty(self) -> bool:
        try:
            return bool(getattr(self.stream, "isatty", lambda: False)())
        except Exception:
            return False

    def draw(self) -> None:
        if not self.enabled:
            return
        self.ensure_map()
        elapsed = time.monotonic() - self.started
        if self.phase == "PROBE" and self.probe_total:
            done, total = self.probe_done, self.probe_total
            label = f"{done}/{total}"
        elif self.phase == "REFRESH" and self.refresh_total:
            done, total = self.refresh_done, self.refresh_total
            label = f"{done}/{total}"
        else:
            done, total, label = 0, 1, "—"
        pct = int(100 * done / max(1, total))
        if not self._is_tty():
            # Line mode for redirected logs / elevated capture — never looks stalled.
            self.stream.write(
                f"[{self.phase}] {label} {pct}% bar={_bar(done, total, 20)} "
                f"off={_fmt_bytes(self.offset)} lat={_fmt_secs(self.latency_s)} "
                f"med={_fmt_secs(self.median_s)} health=m:{self.health.media}/"
                f"t:{self.health.transport}/k:{self.health.mechanical} "
                f"map={''.join(self.map_cells)} | {self.message}\n"
            )
            self.stream.flush()
            return
        lines = [
            "",
            f"+-- In-Place Media Refresh [{self.mode}] {'-' * 34}+",
            f"| Phase: {self.phase:<9} [{_bar(done, total)}] {label:<9} {pct:3d}% |",
            f"| Map:   {''.join(self.map_cells)} |",
            f"|        legend: . pending  o ok  S slow  ! escalate  X error          |",
            f"| Offset {_fmt_bytes(self.offset):>10} / {_fmt_bytes(self.size):<10}  elapsed {_fmt_secs(elapsed):>8}          |",
            f"| Latency now {_fmt_secs(self.latency_s):>7}  median {_fmt_secs(self.median_s):>7}  thr {_fmt_secs(self.threshold_s):>7}     |",
            f"| Rewritten {_fmt_bytes(self.rewritten):>10}  verified {_fmt_bytes(self.verified):<10}                   |",
            f"| Health media={self.health.media:<4} transport={self.health.transport:<4} "
            f"mechanical*={self.health.mechanical:<5} |",
            f"| Journal backend: {self.journal_backend:<8}  (*latency proxy; no acoustic mic)        |",
            f"| {self.message[:70]:<70} |",
        ]
        for item in self.anomalies[-3:]:
            lines.append(f"| ! {item[:68]:<68} |")
        lines.append(f"+{'-' * 72}+")
        out = "\n".join(lines)
        try:
            self.stream.write("\033[2J\033[H")
        except Exception:
            self.stream.write("\n")
        self.stream.write(out + "\n")
        self.stream.flush()

    def finish(self, result: dict) -> None:
        if not self.enabled:
            return
        self.phase = str(result.get("status", "done")).upper()[:12]
        self.rewritten = int(result.get("rewritten_bytes", self.rewritten))
        self.verified = int(result.get("verified_bytes", self.verified))
        self.message = "Run finished — see JSON summary"
        self.draw()
