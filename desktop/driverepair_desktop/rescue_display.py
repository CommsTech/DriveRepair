"""Presentation-only rescue progress; never controls patient disk I/O.

Status and map are derived from committed recovery journal state. In particular,
"recovered" means OS reads were stored, not cryptographic source verification.
Any unexamined region remains unexamined in the visualization.
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from .console_ui import enable_windows_vt, fmt_bytes


def rescue_event(state: dict, *, total: int, phase: str, destination: str,
                 free_bytes: int | None = None, cells: int = 512) -> dict:
    """Translate a durable journal snapshot into a compact, bounded event."""
    cursor = max(0, min(total, int(state.get('cursor', 0))))
    recovered = int(state.get('recovered_bytes', 0))
    missing = state.get('missing_ranges') or []
    pending = state.get('retry_pending_ranges') or []
    unreadable = sum(length for _, length in missing) + sum(length for _, length in pending)
    retry_total = int(state.get('retry_total_bytes') or 0)
    retry_remaining = sum(length for _, length in pending)
    # Map: o = fully processed region, . = not processed, ? = current fractional cell.
    # X marks a processed cell containing known unreadable bytes. Neither o nor X
    # represents file correctness or SMART health. Tiny areas are approximate.
    glyphs = ['.'] * cells
    if total > 0:
        for i in range(cells):
            begin, end = (i * total // cells), ((i + 1) * total // cells)
            if end <= cursor:
                glyphs[i] = 'o'
            elif begin < cursor:
                glyphs[i] = '?'
        for begin, length in [*missing, *pending]:
            if length <= 0:
                continue
            a = min(cells - 1, begin * cells // total)
            b = min(cells - 1, (begin + length - 1) * cells // total)
            for i in range(a, b + 1):
                glyphs[i] = 'X'
    return {
        'workflow': 'rescue', 'phase': phase, 'status': state.get('status', 'in_progress'),
        'total_bytes': total, 'processed_bytes': cursor,
        'recovered_bytes': recovered, 'unreadable_bytes': unreadable,
        'missing_regions': len(missing) + len(pending),
        'retry_total_bytes': retry_total, 'retry_remaining_bytes': retry_remaining,
        'inconsistent_retry_reads': int(state.get('inconsistent_retry_reads', 0)),
        'failed_reads': int(state.get('failed_read_attempts', 0)),
        'destination_free_bytes': free_bytes, 'destination': destination,
        'map': ''.join(glyphs),
    }


def destination_free_space(path: str) -> int | None:
    """Best effort; never let a presentation query fail a recovery."""
    try:
        parent = Path(path).resolve(strict=False).parent
        return shutil.disk_usage(parent).free
    except (OSError, ValueError):
        return None


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return '--'
    n = int(seconds)
    if n >= 86400:
        return f'{n // 86400}d {(n % 86400) // 3600}h'
    if n >= 3600:
        return f'{n // 3600}h {(n % 3600) // 60}m'
    if n >= 60:
        return f'{n // 60}m {n % 60}s'
    return f'{n}s'


class RescueDisplayState:
    """Smoothed measurements, independent of CLI or Tk for deterministic tests."""

    def __init__(self, *, clock=None):
        self.clock = clock or time.monotonic
        self.start = self.clock()
        self.last_time = self.start
        self.last_processed = 0
        self.ema_bytes_per_sec: float | None = None
        self.last_event: dict = {}
        self.last_phase = ''

    def update(self, event: dict) -> dict:
        now = self.clock()
        current = max(0, int(event.get('processed_bytes', 0)))
        phase = str(event.get('phase', 'FORWARD'))
        delta_t = now - self.last_time
        delta_bytes = current - self.last_processed
        if phase != self.last_phase:
            self.ema_bytes_per_sec = None
        if delta_t >= 0.1 and delta_bytes > 0 and phase == self.last_phase:
            rate = delta_bytes / delta_t
            self.ema_bytes_per_sec = (rate if self.ema_bytes_per_sec is None
                                      else 0.25 * rate + 0.75 * self.ema_bytes_per_sec)
        self.last_phase = phase
        self.last_time = now
        self.last_processed = current
        total = max(0, int(event.get('total_bytes', 0)))
        rate = self.ema_bytes_per_sec
        # Retry passes have nonmonotonic position and no honest wall-clock ETA.
        eta = ((total - current) / rate if rate and phase == 'FORWARD' and current < total
               else None)
        self.last_event = {**event, 'speed_bytes_per_sec': rate,
                           'eta_seconds': eta, 'elapsed_seconds': now - self.start,
                           'percent': 100 * current / total if total else 0.0}
        return self.last_event


class RescueTerminal:
    """Throttled human-readable CLI, with single-line TTY updates and sparse logs."""

    def __init__(self, *, stream=None, tty=None, clock=None):
        self.stream = stream or sys.stderr
        self.clock = clock or time.monotonic
        self.tty = bool(self.stream.isatty()) if tty is None else tty
        if os.name == 'nt' and self.tty and not enable_windows_vt():
            self.tty = False  # Old Windows console: avoid printing raw ANSI codes.
        self.last_print = -1e10
        self.last_percent = -1
        self.active_line = False
        self.state = RescueDisplayState(clock=self.clock)

    def show(self, event: dict, *, force: bool = False) -> None:
        view = self.state.update(event)
        now = self.clock()
        percent = int(view['percent'])
        # Redirected output receives sparse milestones, not thousands of raw lines.
        if not force and (now - self.last_print < (0.5 if self.tty else 60.0)):
            return
        if not self.tty and not force and percent == self.last_percent and now - self.last_print < 60:
            return
        self.last_print = now
        self.last_percent = percent
        speed = (f"{fmt_bytes(int(view['speed_bytes_per_sec']))}/s"
                 if view['speed_bytes_per_sec'] else 'calculating')
        eta = format_duration(view['eta_seconds'])
        phase = 'Retry pass' if view.get('phase') == 'RETRY' else 'Rescue'
        text = (f"{phase}  {view['percent']:5.1f}%  "
                f"{fmt_bytes(view['recovered_bytes'])} saved  "
                f"{fmt_bytes(view['unreadable_bytes'])} unreadable  "
                f"{speed}  ETA {eta}")
        if self.tty:
            width = max(20, shutil.get_terminal_size((110, 25)).columns - 1)
            text = text[:width]
            self.stream.write('\r\033[2K' + text)
            self.active_line = True
        else:
            self.stream.write(text + '\n')
        self.stream.flush()

    def finish(self) -> None:
        if self.active_line:
            self.stream.write('\n')
            self.stream.flush()
            self.active_line = False
