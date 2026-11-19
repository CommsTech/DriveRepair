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
        # Preserve read evidence across throttled messages. Otherwise the UI
        # falsely shows 15% coverage after a full 100% sequential read.
        self._read_spans: list[list] = []
        self._read_phase: str | None = None

    def emit(self, event: dict, *, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        phase = str(event.get('phase') or '')
        if phase != self._read_phase:
            # A phase transition must not associate old read spans with a
            # different operation (e.g. completed scan -> writing). A final
            # forced SCANNING event flushes all buffered evidence.
            self._read_spans.clear()
            self._read_phase = phase
        if phase == 'SCANNING':
            offset, length = event.get('offset'), event.get('read_length')
            if type(offset) is int and type(length) is int and offset >= 0 and length > 0:
                failed = bool(event.get('failed'))
                slow = bool(event.get('slow'))
                prior = self._read_spans[-1] if self._read_spans else None
                if prior and prior[0] + prior[1] == offset and prior[2:] == [failed, slow]:
                    prior[1] += length
                else:
                    self._read_spans.append([offset, length, failed, slow])
        if not force and now - self._last < self.min_interval_s and len(self._read_spans) < 512:
            return
        self._last = now
        payload = {"type": "progress", "ts": round(time.time(), 3), **event}
        if self._read_spans:
            payload['observed_read_spans'] = self._read_spans
            self._read_spans = []
        try:
            self.stream.write(json.dumps(payload, separators=(",", ":")) + "\n")
            self.stream.flush()
        except Exception:
            # Presentation must never abort recovery.
            pass
