"""Live console dashboard for In-Place Media Refresh.

Designed for PowerShell / Windows Terminal / macOS / Linux:
- One in-place panel when stderr is a real console (no scrolling wall)
- Compact throttled lines when redirected / piped
- ASCII-only glyphs (no mojibake ellipsis on cp1252 consoles)
- Optional ANSI color when VT is available

mechanical* is a latency/error proxy — USB docks have no acoustic mic.
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field

from . import console_ui as ui


def _bar(done: int, total: int, width: int = 28) -> str:
    return ui.progress_bar(done, total, width)


def _fmt_bytes(n: int) -> str:
    return ui.fmt_bytes(n)


def _fmt_secs(seconds: float | None) -> str:
    return ui.fmt_secs(seconds)


@dataclass
class HealthIndicators:
    media: str = "UNKNOWN"          # OK | WARN | FAIL | UNKNOWN
    transport: str = "UNKNOWN"      # OK | WARN | FAIL | UNKNOWN
    mechanical: str = "UNKNOWN"     # OK | WATCH | FAIL | UNKNOWN


@dataclass
class RefreshDashboard:
    mode: str
    size: int
    enabled: bool = True
    stream: object = field(default_factory=lambda: sys.stderr)
    emitter: object | None = None  # ProgressEmitter | None
    phase: str = "START"
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
    map_width: int = 48
    message: str = ""
    started: float = field(default_factory=time.monotonic)
    _last_draw: float = 0.0
    _last_line_key: str = ""
    _panel_rows: int = 0
    anomalies: list[str] = field(default_factory=list)
    device_label: str = ""

    def ensure_map(self) -> None:
        if len(self.map_cells) != self.map_width:
            self.map_cells = ["."] * self.map_width

    def mark_map(self, offset: int, symbol: str) -> None:
        self.ensure_map()
        if self.size <= 0:
            return
        idx = min(self.map_width - 1, int(offset * self.map_width / self.size))
        rank = {".": 0, "o": 1, "S": 2, "!": 3, "X": 4}
        if rank.get(symbol, 0) >= rank.get(self.map_cells[idx], 0):
            self.map_cells[idx] = symbol

    def note_anomaly(self, text: str) -> None:
        # Strip non-ASCII so Windows cp1252 consoles never show garbage.
        clean = text.encode("ascii", "replace").decode("ascii")
        if clean not in self.anomalies:
            self.anomalies.append(clean)
            if len(self.anomalies) > 4:
                self.anomalies = self.anomalies[-4:]

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
            if self.health.mechanical in {"UNKNOWN", "OK"}:
                self.health.mechanical = "WATCH"
            self.note_anomaly(f"High latency {_fmt_secs(latency)} (mech*/USB proxy)")
        if event.get("mechanical_fail"):
            self.health.mechanical = "FAIL"
            self.note_anomaly("Mechanical-suspect pattern: extreme latency streak")
        # Promote UNKNOWN -> OK after successful probe/refresh samples with no errors.
        if not event.get("failed") and not kind:
            if self.health.media == "UNKNOWN":
                self.health.media = "OK"
            if self.health.transport == "UNKNOWN":
                self.health.transport = "OK"
            if self.health.mechanical == "UNKNOWN" and self.phase in {"PROBE", "REFRESH"}:
                self.health.mechanical = "OK"

    def handle(self, event: dict) -> None:
        if not self.enabled and self.emitter is None:
            return
        status = event.get("status") or event.get("phase") or self.phase
        if status in {"starting", "start"}:
            self.phase = "START"
            self.message = event.get("message") or "Opening patient"
        elif status == "probing" or event.get("phase") == "probe":
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
            self.message = event.get("message") or (
                f"Probe {self.probe_done}/{self.probe_total} @ {_fmt_bytes(self.offset)}"
            )
        elif status in {"in_progress", "refreshing"} or event.get("phase") == "refresh":
            self.phase = "REFRESH"
            self.refresh_done = int(event.get("refresh_index", self.refresh_done))
            self.refresh_total = int(event.get("refresh_total", self.refresh_total))
            self.rewritten = int(event.get("rewritten_bytes", self.rewritten))
            self.verified = int(event.get("verified_bytes", self.verified))
            self.offset = int(event.get("offset", self.offset))
            self.message = event.get("message") or f"Rewrite @ {_fmt_bytes(self.offset)}"
            self.mark_map(self.offset, "S")
        elif status == "escalating" or event.get("phase") == "escalate":
            self.phase = "ESCALATE"
            self.message = event.get("message") or "Auto-escalate deeper test"
            self.mark_map(int(event.get("offset", self.offset)), "!")
        if event.get("error_class") or event.get("mechanical_fail") or event.get("latency_s") or (
            status in {"probing", "refreshing", "in_progress"} and not event.get("failed")
        ):
            self.update_health_from_event(event)
        now = time.monotonic()
        force = bool(event.get("force") or event.get("failed") or event.get("mechanical_fail")
                     or status in {"starting", "escalating"})
        if self.emitter is not None:
            self.emitter.emit(
                {
                    "phase": self.phase,
                    "probe_index": self.probe_done,
                    "probe_total": self.probe_total,
                    "refresh_index": self.refresh_done,
                    "refresh_total": self.refresh_total,
                    "offset": self.offset,
                    "size": self.size,
                    "latency_ms": None if self.latency_s is None else round(self.latency_s * 1000, 3),
                    "median_ms": None if self.median_s is None else round(self.median_s * 1000, 3),
                    "threshold_ms": None if self.threshold_s is None else round(self.threshold_s * 1000, 3),
                    "rewritten_bytes": self.rewritten,
                    "verified_bytes": self.verified,
                    "health": {
                        "media": self.health.media,
                        "transport": self.health.transport,
                        "mechanical": self.health.mechanical,
                    },
                    "map": "".join(self.map_cells) if self.map_cells else "",
                    "message": self.message,
                    "journal_backend": self.journal_backend,
                    "mode": self.mode,
                },
                force=force or bool(event.get("failed") or event.get("mechanical_fail")),
            )
        # Panel ~8 Hz; redirected line mode ~2 Hz unless forced.
        min_interval = 0.12 if self._is_tty() else 0.45
        if self.enabled and (force or now - self._last_draw >= min_interval):
            self.draw()
            self._last_draw = now

    def _is_tty(self) -> bool:
        forced = os.environ.get("DRIVEREPAIR_FORCE_TTY_DASHBOARD", "").strip().lower()
        if forced in {"1", "true", "yes", "on"}:
            return True
        if forced in {"0", "false", "no", "off", "line"}:
            return False
        try:
            return bool(getattr(self.stream, "isatty", lambda: False)())
        except Exception:
            return False

    def _progress(self) -> tuple[int, int, str, int]:
        if self.phase == "PROBE" and self.probe_total:
            done, total = self.probe_done, self.probe_total
        elif self.phase == "REFRESH" and self.refresh_total:
            done, total = self.refresh_done, self.refresh_total
        else:
            done, total = 0, 1
        label = f"{done}/{total}" if total else "--"
        pct = int(100 * done / max(1, total))
        return done, total, label, pct

    def _health_colored(self) -> str:
        text = ui.health_compact(self.health.media, self.health.transport, self.health.mechanical)
        worst = self.health.media, self.health.transport, self.health.mechanical
        if "FAIL" in worst:
            return ui.paint(text, ui.RED, stream=self.stream)
        if "WATCH" in worst or "WARN" in worst:
            return ui.paint(text, ui.YELLOW, stream=self.stream)
        if all(v in {"OK", "UNKNOWN"} for v in worst) and "OK" in worst:
            return ui.paint(text, ui.GREEN, stream=self.stream)
        return ui.paint(text, ui.DIM, stream=self.stream)

    def _phase_colored(self) -> str:
        code = {
            "PROBE": ui.CYAN,
            "REFRESH": ui.YELLOW,
            "ESCALATE": ui.RED,
            "START": ui.DIM,
        }.get(self.phase, ui.WHITE)
        return ui.paint(f"{self.phase:<8}", code, ui.BOLD, stream=self.stream)

    def _render_map(self) -> str:
        self.ensure_map()
        if not ui.color_enabled(self.stream):
            return "".join(self.map_cells)
        out = []
        for ch in self.map_cells:
            if ch == "o":
                out.append(ui.paint(ch, ui.GREEN, stream=self.stream))
            elif ch == "S":
                out.append(ui.paint(ch, ui.YELLOW, stream=self.stream))
            elif ch == "!":
                out.append(ui.paint(ch, ui.YELLOW, ui.BOLD, stream=self.stream))
            elif ch == "X":
                out.append(ui.paint(ch, ui.RED, ui.BOLD, stream=self.stream))
            else:
                out.append(ui.paint(ch, ui.DIM, stream=self.stream))
        return "".join(out)

    def draw(self) -> None:
        if not self.enabled:
            return
        ui.enable_windows_vt()
        done, total, label, pct = self._progress()
        elapsed = time.monotonic() - self.started
        bar = _bar(done, total, 28)
        if not self._is_tty():
            # Compact single-line mode for logs / pipes (no wall of duplicate health/map).
            key = f"{self.phase}:{label}:{pct}:{self.offset}:{self.message}"
            if key == self._last_line_key and self.phase not in {"START"}:
                return
            self._last_line_key = key
            line = (
                f"{self.phase:<8} {label:>7} {pct:3d}% {bar}  "
                f"off={_fmt_bytes(self.offset):>10}  "
                f"lat={_fmt_secs(self.latency_s):>6} med={_fmt_secs(self.median_s):>6}  "
                f"{ui.health_compact(self.health.media, self.health.transport, self.health.mechanical)}  "
                f"| {self.message}"
            )
            self.stream.write(line[:220] + "\n")
            self.stream.flush()
            return

        title = f"DriveRepair  In-Place Refresh  [{self.mode}/{self.journal_backend}]"
        if self.device_label:
            title += f"  {self.device_label}"
        msg = self.message.encode("ascii", "replace").decode("ascii")[:68]
        lines = [
            ui.paint("+" + "-" * 74 + "+", ui.CYAN, stream=self.stream),
            ui.paint("| ", ui.CYAN, stream=self.stream)
            + ui.paint(f"{title:<72}", ui.BOLD, stream=self.stream)
            + ui.paint(" |", ui.CYAN, stream=self.stream),
            ui.paint("+" + "-" * 74 + "+", ui.CYAN, stream=self.stream),
            f"| Phase  {self._phase_colored()}  {bar}  {label:<9} {pct:3d}%",
            f"| Map    {self._render_map()}",
            f"|        {ui.paint(ui.map_legend(), ui.DIM, stream=self.stream)}",
            f"| Pos    {_fmt_bytes(self.offset):>10} / {_fmt_bytes(self.size):<10}"
            f"     elapsed {_fmt_secs(elapsed):>8}",
            f"| Lat    now {_fmt_secs(self.latency_s):>7}   median {_fmt_secs(self.median_s):>7}"
            f"   thr {_fmt_secs(self.threshold_s):>7}",
            f"| Work   rewritten {_fmt_bytes(self.rewritten):>10}"
            f"   verified {_fmt_bytes(self.verified):<10}",
            f"| Health {self._health_colored()}",
            f"| Status {msg}",
        ]
        for item in self.anomalies[-2:]:
            lines.append(
                f"| {ui.paint('!', ui.YELLOW, stream=self.stream)} "
                f"{item[:70]:<70} |"
            )
        lines.append(ui.paint("+" + "-" * 74 + "+", ui.CYAN, stream=self.stream))
        # In-place redraw: home cursor + clear-down (keeps one panel, not a scroll flood).
        try:
            self.stream.write("\033[H\033[J")
        except Exception:
            self.stream.write("\n")
        body = "\n".join(lines) + "\n"
        self.stream.write(body)
        self.stream.flush()
        self._panel_rows = len(lines)

    def finish(self, result: dict) -> None:
        if not self.enabled:
            return
        self.phase = str(result.get("status", "done")).upper()[:12]
        self.rewritten = int(result.get("rewritten_bytes", self.rewritten))
        self.verified = int(result.get("verified_bytes", self.verified))
        self.message = "Finished - see summary below"
        self.draw()
        # Leave the final panel on screen, then a blank line before JSON.
        try:
            self.stream.write("\n")
            self.stream.flush()
        except Exception:
            pass
