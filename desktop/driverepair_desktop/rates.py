"""Actual recent-window throughput; not total bytes divided by total runtime."""
from __future__ import annotations
from typing import Any
from collections import deque
import time

class RateWindow:
    def __init__(self, seconds: float = 5.0):
        self.seconds = seconds
        self.points: deque[tuple[float, int]] = deque()

    def update(self, byte_count: int, now: float | None = None) -> float | None:
        now = time.monotonic() if now is None else now
        if self.points and (now < self.points[-1][0] or byte_count < self.points[-1][1]):
            self.points.clear()
        self.points.append((now, byte_count))
        while len(self.points) > 2 and now - self.points[1][0] >= self.seconds:
            self.points.popleft()
        if len(self.points) < 2:
            return None
        elapsed = now - self.points[0][0]
        if elapsed <= 0:
            return None
        return max(0.0, (byte_count - self.points[0][1]) / elapsed)


def choose_speed(speed_bps: Any, average_bps: float | None = None, *, finished: bool = False) -> tuple[float | None, bool]:
    """Pick the throughput value the UI should show.

    A job short enough to finish inside one rate-window sample never produces a
    recent-speed value. Rather than leaving "Measuring…" on screen after the
    work is done, fall back to the measured average once the job has finished.

    Returns ``(bytes_per_second, is_average)``; ``(None, False)`` means no
    measurement exists yet and the caller should keep its placeholder.
    """
    try:
        value = float(speed_bps)
    except (TypeError, ValueError):
        value = 0.0
    if value > 0:
        return value, False
    if finished and average_bps is not None:
        try:
            average = float(average_bps)
        except (TypeError, ValueError):
            average = 0.0
        if average > 0:
            return average, True
    return None, False
