"""Actual recent-window throughput; not total bytes divided by total runtime."""
from __future__ import annotations
from collections import deque
import time

class RateWindow:
    def __init__(self, seconds: float = 5.0):
        self.seconds = seconds
        self.points = deque()

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
