"""No raw devices: targeted retry and decision-model failure injection."""
from __future__ import annotations

import errno
from pathlib import Path
import tempfile
import unittest

from driverepair_desktop.recovery import rescue_reader, inspect_rescue_status
from driverepair_desktop.qtgui import progress_percent
from driverepair_desktop.guided_repair import plan_targeted_refresh
from driverepair_desktop.rescue_display import rescue_event

SECTOR = 512


class FaultReader:
    def __init__(self, patient: bytes, bad: set[int] = frozenset(), transient=False,
                 alternate=False):
        self.patient = patient
        self.bad = bad
        self.transient = transient
        self.alternate = alternate
        self.seen: dict[tuple[int, int], int] = {}
        self.writes = 0

    def read_at(self, offset: int, count: int) -> bytes:
        key = (offset, count)
        self.seen[key] = self.seen.get(key, 0) + 1
        if any(offset <= p < offset + count for p in self.bad):
            if (not self.transient and not self.alternate) or count != SECTOR or self.seen[key] == 1:
                raise OSError(errno.EIO, 'Injected failed read')
        payload = self.patient[offset:offset + count]
        if self.alternate and offset == 512 and count == SECTOR:
            if self.seen[key] % 2 == 0:
                return bytes([payload[0] ^ 1]) + payload[1:]
        return payload


class RecoveryOptimizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = str(Path(self.tmp.name) / 'rescued.img')
        self.source = bytes((i % 251 for i in range(4096)))

    def copy(self, reader, **options):
        return rescue_reader(reader, size=len(self.source), sector=SECTOR,
                             output=self.output, source_token='same-source',
                             chunk=1024, **options)

    def test_transient_failed_sector_recovers_real_exact_bytes(self):
        reader = FaultReader(self.source, bad={512}, transient=True)
        first = self.copy(reader)
        self.assertEqual(first['missing_ranges'], [[0, 1024]])
        # The original chunk fails; targeted retry subdivides until 512 bytes.
        second = self.copy(reader, resume=True, retry_missing=True)
        self.assertEqual(second['missing_ranges'], [])
        self.assertEqual(second['recovered_bytes'], len(self.source))
        self.assertEqual(Path(self.output).read_bytes(), self.source)
        self.assertTrue(inspect_rescue_status(self.output)['clean_rescue_complete'])
        self.assertEqual(reader.writes, 0)

    def test_unstable_bytes_never_written_or_marked_recovered(self):
        reader = FaultReader(self.source, bad={512}, alternate=True)
        self.copy(reader)
        second = self.copy(reader, resume=True, retry_missing=True)
        self.assertEqual(second['missing_ranges'], [[512, SECTOR]])
        self.assertEqual(second['recovered_bytes'], len(self.source) - SECTOR)
        self.assertGreater(second['inconsistent_retry_reads'], 0)
        self.assertEqual(Path(self.output).read_bytes()[512:1024], b'\0' * SECTOR)
        self.assertFalse(inspect_rescue_status(self.output)['clean_rescue_complete'])
        self.assertEqual(reader.writes, 0)

    def test_unrecoverable_sector_is_bounded(self):
        reader = FaultReader(self.source, bad={512})
        self.copy(reader)
        state = self.copy(reader, resume=True, retry_missing=True,
                          retry_sector_attempts=2)
        self.assertEqual(state['missing_ranges'], [[512, SECTOR]])
        self.assertLess(sum(reader.seen.values()), 25)

    def test_rescue_phase_progress_uses_retry_work_not_source_cursor(self):
        state = {'cursor': 4096, 'recovered_bytes': 3584,
                 'missing_ranges': [], 'retry_pending_ranges': [[512, 512]],
                 'retry_total_bytes': 1024, 'status': 'retry_in_progress'}
        event = rescue_event(state, total=4096, phase='RETRY', destination=self.output)
        self.assertEqual(event['retry_remaining_bytes'], 512)
        self.assertEqual(progress_percent(event), 50.0)
        forward = rescue_event({**state, 'cursor':2048}, total=4096,
                               phase='FORWARD', destination=self.output)
        self.assertEqual(progress_percent(forward), 50.0)

    def test_limited_write_plan_prioritizes_confirmed_weakest_regions(self):
        scan = {'status': 'completed_with_slow_regions', 'mode': 'full',
                'device_size_bytes': 4096, 'read_error_chunks': 0,
                'slow_regions': [
                    {'offset': 0, 'latency_ms': 100},
                    {'offset': 1024, 'latency_ms': 900},
                    {'offset': 2048, 'latency_ms': 500}]}
        plan = plan_targeted_refresh(scan, sector=512, chunk=512, max_regions=2)
        self.assertEqual(plan['targets'], [(1024, 512), (2048, 512)])
        self.assertTrue(plan['unresolved_data'])
        self.assertEqual(plan['batch_selection'], 'repeatable_error_then_slow_latency')


if __name__ == '__main__':
    unittest.main()
