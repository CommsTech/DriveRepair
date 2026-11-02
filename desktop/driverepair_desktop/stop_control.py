"""Cooperative cancellation requested by a trusted local UI over child stdin.

No disk/journal files, no signals, and no unverified asynchronous write abort.
The engine checks only at safe boundaries. A blocked kernel read cannot be
forcibly cancelled by this mechanism.
"""
from __future__ import annotations

import sys
from threading import Event, Thread


class StopRequested(Exception):
    """Stop requested at a safe boundary, without stopping an active write."""


class StopControl:
    def __init__(self, enabled: bool = False):
        self._requested = Event()
        if enabled:
            Thread(target=self._listen, daemon=True, name='driverepair-stop-listener').start()

    def _listen(self):
        for line in sys.stdin:
            if line.strip().upper() == 'STOP':
                self._requested.set()
                break

    def requested(self) -> bool:
        return self._requested.is_set()

    def check_read_boundary(self) -> None:
        if self.requested():
            raise StopRequested('Cancelled before further patient I/O')
