"""Truthful, whole-device progress aggregation for sparse or full scans.

Each fixed grid cell represents the same fraction of the drive, independent of
scan order. A successful *sample* fills only the fraction actually read.  Failed
reads are observations of failed I/O requests, not proof of every byte being bad.
Memory is bounded for sequential passes by merging adjacent intervals.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field


@dataclass
class CoverageCell:
    start: int
    end: int
    intervals: list[tuple[int, int]] = field(default_factory=list)
    read_errors: int = 0
    slow_reads: int = 0
    covered_bytes: int = 0

    @property
    def checked_bytes(self) -> int:
        return self.covered_bytes

    @property
    def fraction(self) -> float:
        return self.checked_bytes / max(1, self.end - self.start)

    def record(self, start: int, stop: int, *, failed: bool = False, slow: bool = False) -> None:
        start = max(self.start, start)
        stop = min(self.end, stop)
        if stop <= start:
            return
        if failed:
            self.read_errors += 1
            return
        if slow:
            self.slow_reads += 1
        # Intervals remain sorted and disjoint. A binary insertion search plus
        # localized merging avoids re-sorting the entire history at every read.
        intervals = self.intervals
        index = bisect_left(intervals, (start, -1))
        if index and intervals[index - 1][1] >= start:
            index -= 1
        last = index
        removed = 0
        while last < len(intervals) and intervals[last][0] <= stop:
            lo, hi = intervals[last]
            start = min(start, lo)
            stop = max(stop, hi)
            removed += hi - lo
            last += 1
        intervals[index:last] = [(start, stop)]
        self.covered_bytes += stop - start - removed


class SurfaceCoverage:
    def __init__(self, size: int = 0, cells: int = 384):
        if cells < 1:
            raise ValueError('at least one map cell required')
        self.cells_count = cells
        self.reset(size)

    def reset(self, size: int) -> None:
        if size < 0:
            raise ValueError('negative drive capacity')
        self.size = size
        self.cells = [CoverageCell(size * i // self.cells_count,
                                   size * (i + 1) // self.cells_count)
                      for i in range(self.cells_count)]

    def observe(self, offset: int, length: int, *, failed: bool = False,
                slow: bool = False) -> None:
        if self.size <= 0 or offset < 0 or length <= 0 or offset >= self.size:
            return
        stop = min(self.size, offset + length)
        first = min(self.cells_count - 1, offset * self.cells_count // self.size)
        last = min(self.cells_count - 1, (stop - 1) * self.cells_count // self.size)
        for i in range(first, last + 1):
            self.cells[i].record(offset, stop, failed=failed, slow=slow)

    @property
    def checked_bytes(self) -> int:
        return sum(c.checked_bytes for c in self.cells)

    @property
    def coverage_pct(self) -> float:
        return 100.0 * self.checked_bytes / self.size if self.size else 0.0
