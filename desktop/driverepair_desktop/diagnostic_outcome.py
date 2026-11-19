"""Evidence-led classification for completed read-only scans.

A diagnostic can finish its planned sample while returning a nonzero code
because some reads failed. That result requires attention, but it is not an
interrupted worker or a completed repair. Keep this decision testable without
loading PySide6 or accessing real disks.
"""
from __future__ import annotations
from dataclasses import dataclass

SCAN_WORKFLOWS = frozenset({'scanquick', 'scanfull', 'resume'})

@dataclass(frozen=True)
class ScanOutcome:
    headline: str
    summary: str
    recommendation: str
    complete: bool


def classify_scan_outcome(result: dict, exit_code: int, workflow: str) -> ScanOutcome | None:
    if workflow not in SCAN_WORKFLOWS or not isinstance(result, dict):
        return None
    status = result.get('status')
    if status == 'completed_with_read_errors' and exit_code in (0, 2):
        try:
            count = int(result.get('read_error_chunks') or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            return None
        return ScanOutcome(
            headline='Scan completed · read errors detected',
            summary=f'{count} failed read requests were recorded. The selected scan finished, '
                    'but some sampled data could not be read. These are not confirmed bad-sector counts.',
            recommendation='Rescue important data to a separate healthy disk. Use Address scan errors '
                           'to recheck the saved failing locations without repeating the whole scan.',
            complete=True,
        )
    if exit_code == 0 and status in {'completed', 'scan_completed'}:
        return ScanOutcome(
            headline='Diagnostic scan completed',
            summary='Selected read-only scan finished; this does not certify file integrity or drive life.',
            recommendation='Review measured coverage, then back up important files before taking action.',
            complete=True,
        )
    return None
