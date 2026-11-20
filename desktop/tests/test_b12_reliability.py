"""Regression checks for bounded I/O and safe guided cancellation."""
import errno
import tempfile
import unittest
from pathlib import Path

from driverepair_desktop.guided_repair import investigate_failed_ranges
from driverepair_desktop.media_refresh import refresh_media
from driverepair_desktop.qtgui import estimated_job_percent
from driverepair_desktop.stop_control import StopRequested


class FailingReader:
    def __init__(self):
        self.attempts = 0

    def read_at(self, offset, length):
        self.attempts += 1
        raise OSError(errno.EIO, 'simulated unreadable media')


class InMemoryPatient:
    def __init__(self):
        self.bytes = bytearray(b'A' * 4096)
        self.writes = []

    def read_at(self, offset, length):
        return bytes(self.bytes[offset:offset + length])

    def write_at(self, offset, content):
        self.writes.append((offset, len(content)))
        self.bytes[offset:offset + len(content)] = content
        return len(content)

    def flush(self):
        pass


class BoundedInvestigationTests(unittest.TestCase):
    def test_every_failed_request_counts_and_budget_holds(self):
        reader = FailingReader()
        events = []
        report = investigate_failed_ranges(
            reader, [{'offset': 0, 'length': 1024*1024}],
            sector=512, max_reads=8, progress=events.append)
        self.assertEqual(reader.attempts, 8)
        self.assertEqual(report['read_calls'], 8)
        self.assertTrue(report['budget_exhausted'])
        self.assertGreater(len(report['unresolved_regions']), 0)
        self.assertTrue(events)
        self.assertEqual(events[-1]['max_reads'], 8)

    def test_stopped_before_next_io_call(self):
        reader = FailingReader()
        def stop(_event):
            raise StopRequested('simulated user stop')
        with self.assertRaises(StopRequested):
            investigate_failed_ranges(reader, [{'offset': 0, 'length': 8192}],
                                      sector=512, max_reads=8, progress=stop)
        self.assertEqual(reader.attempts, 0)

    def test_statuses_separate_scan_investigation_and_refresh(self):
        scan = {'phase': 'SCANNING', 'probe_index': 95, 'probe_total': 100}
        probe = {'phase': 'INVESTIGATING', 'investigation_reads': 6,
                 'investigation_total': 24}
        repair = {'phase': 'REFRESH', 'refresh_index': 1, 'refresh_total': 2}
        self.assertEqual(estimated_job_percent(scan, guided=False), 95)
        self.assertAlmostEqual(estimated_job_percent(scan, guided=True), 57)
        self.assertAlmostEqual(estimated_job_percent(probe, guided=True), 63.75)
        self.assertAlmostEqual(estimated_job_percent(repair, guided=True), 87.5)


class SafeStopTests(unittest.TestCase):
    def test_pre_requested_stop_skips_all_writes(self):
        patient = InMemoryPatient()
        with tempfile.TemporaryDirectory() as td:
            result = refresh_media(patient, size=4096, sector=512,
                source_token='synthetic', journal=str(Path(td)/'journal'),
                chunk=512, mode='targeted', targets=[(0, 512), (1024, 512)],
                stop_requested=lambda: True)
        self.assertEqual(result['status'], 'stopped_at_safe_boundary')
        self.assertEqual(patient.writes, [])

    def test_stop_between_transactions_never_leaves_active_region(self):
        patient = InMemoryPatient()
        should_stop = [False]
        def progress(info):
            if int(info.get('rewritten_bytes') or 0) >= 512 and not info.get('transaction'):
                should_stop[0] = True
        with tempfile.TemporaryDirectory() as td:
            result = refresh_media(patient, size=4096, sector=512,
                source_token='synthetic', journal=str(Path(td)/'journal'),
                chunk=512, mode='targeted', targets=[(0, 512), (1024, 512)],
                progress=progress, stop_requested=lambda: should_stop[0])
        self.assertEqual(result['status'], 'stopped_at_safe_boundary')
        self.assertEqual(patient.writes, [(0, 512)])
        self.assertIsNone(result['transaction'])
        self.assertEqual(patient.bytes, b'A'*4096)


if __name__ == '__main__':
    unittest.main()
