"""Low-overhead structured progress events for CLI and GUI consumers.

Recovery I/O remains the priority. Presentation may emit at most ~10 Hz.
Events are single-line JSON on a dedicated stream (typically stderr) so
stdout can stay machine-readable for final results.
"""
from __future__ import annotations

import json
import sys
import time
from typing import TextIO


class ProgressEmitter:
    def __init__(
        self,
        enabled: bool = False,
        stream: TextIO | None = None,
        min_interval_s: float = 0.1,
    ) -> None:
        self.enabled = enabled
        self.stream = stream or sys.stderr
        self.min_interval_s = min_interval_s
        self._last = 0.0

    def emit(self, event: dict, *, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        if not force and (now - self._last) < self.min_interval_s:
            return
        self._last = now
        payload = {"type": "progress", "ts": round(time.time(), 3), **event}
        try:
            self.stream.write(json.dumps(payload, separators=(",", ":")) + "\n")
            self.stream.flush()
        except Exception:
            # Presentation must never abort recovery.
            pass
