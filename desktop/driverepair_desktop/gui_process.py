"""Pure, display-agnostic CLI child command contract for Qt and tests."""
from __future__ import annotations
import os
import sys


def recovery_command(args: list[str], *, executable: str | None = None,
                     entrypoint: str | None = None) -> list[str]:
    python = executable or sys.executable
    entry = entrypoint if entrypoint is not None else sys.argv[0]
    if entry.lower().endswith('.pyz') and os.path.isfile(entry):
        return [python, os.path.abspath(entry), *args]
    return [python, '-m', 'driverepair_desktop', *args]

PROGRESS_OPERATIONS = frozenset({
    'rescue-image', 'rescue-external', 'rescue-system',
    'scan', 'scan-image', 'care-image', 'care-external',
    'refresh-image', 'refresh-external', 'refresh-system',
    'benchmark-external', 'last-resort-system-refresh',
})
COOPERATIVE_STOP_OPERATIONS = frozenset({
    'scan', 'scan-image', 'care-image', 'care-external',
    'refresh-image', 'refresh-external', 'refresh-system',
})


def prepare_child_arguments(args: list[str]) -> list[str]:
    result = list(args)
    if result and result[0] in PROGRESS_OPERATIONS and '--progress-jsonl' not in result:
        result.extend(['--progress-jsonl', '--no-live-dashboard'])
    if result and result[0] in COOPERATIVE_STOP_OPERATIONS and '--cooperative-stop-stdin' not in result:
        result.append('--cooperative-stop-stdin')
    return result
