"""No hardware I/O: adversarial synthetic tests for staged adaptive scanning."""
import errno
import os
import tempfile
import unittest
from pathlib import Path

from driverepair_desktop.adaptive_scan import adaptive_full_scan, classify_error
from driverepair_desktop.scanner import scan_reader
from driverepair_desktop.scan_history import load_hints, save_hints
from driverepair_desktop.guided_repair import plan_targeted_refresh

MIB = 1024 * 1024


class FakeReader:
    def __init__(self, size, bad=None, deny=False):
        self.size = size
        self.bad = bad or []
        self.deny = deny
        self.read_calls = []
        self.writes = 0

    def read_at(self, off, count):
        self.read_calls.append((off, count))
        if self.deny:
            raise PermissionError(errno.EACCES, 'access denied')
        for a, b in self.bad:
            if off < b and a < off + count:
                # Windows ctypes.WinError(ERROR_IO_DEVICE) can have errno=22
                err = OSError(errno.EINVAL, 'I/O error')
                err.winerror = 1117
                raise err
        return b'\xB5' * count

    def close(self):
        pass


class AdaptiveReadTests(unittest.TestCase):
    def test_native_1117_is_io_not_invalid_argument(self):
        err = OSError(errno.EINVAL, 'IO failure')
        err.winerror = 1117
        self.assertEqual(classify_error(err), 'io_device_error_unconfirmed_media')
        self.assertEqual(classify_error(OSError(errno.EINVAL, 'invalid request')),
                         'invalid_read_request')

    def test_bad_region_is_deferred_and_good_area_after_it_is_scanned(self):
        size = 32 * MIB
        r = FakeReader(size, bad=[(5 * MIB, 6 * MIB)])
        events = []
        result = adaptive_full_scan(r, size=size, sector=512, chunk=MIB,
                                    min_chunk=MIB, max_chunk=2*MIB,
                                    max_errors=2, max_followup_reads=16,
                                    progress=lambda current,total,info: events.append((current,total,info)))
        self.assertEqual(result['status'], 'completed_with_read_errors')
        self.assertGreater(result['readable_bytes'], 16 * MIB)
        self.assertTrue(any(off >= 24*MIB for off,count in r.read_calls))
        self.assertTrue(result['read_error_ranges'])
        self.assertEqual(result['read_error_ranges'][0]['interpretation'],
                         'io_device_error_unconfirmed_media')
        self.assertTrue(result['error_investigation']['unresolved_regions'])
        self.assertEqual(r.writes, 0)
        self.assertTrue(all(0 <= cur <= total for cur,total,inf in events))

    def test_clean_drive_grows_read_size_without_benchmarking_file_data(self):
        r = FakeReader(80*MIB)
        result = adaptive_full_scan(r, size=80*MIB, sector=512,
                                    chunk=MIB, min_chunk=MIB, max_chunk=8*MIB)
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(any(c > MIB for o,c in r.read_calls))
        self.assertEqual(result['readable_bytes'], 80*MIB)
        self.assertEqual(r.writes, 0)

    def test_access_denied_stops_immediately_not_false_success(self):
        r = FakeReader(8*MIB, deny=True)
        result = adaptive_full_scan(r, size=8*MIB, sector=512, chunk=MIB)
        self.assertEqual(result['status'], 'aborted_device_or_access_error')
        self.assertEqual(result['readable_bytes'], 0)
        self.assertLess(result['surface_coverage_pct'], 100)

    def test_scanner_full_adaptive_wired_to_public_api(self):
        r = FakeReader(24*MIB, bad=[(MIB, 2*MIB)])
        result = scan_reader(r, size=24*MIB, sector=512,
                             mode='full', chunk=MIB, adaptive_io=True, max_errors=2)
        self.assertTrue(result['adaptive_io'])
        self.assertGreater(result['readable_bytes'], 15*MIB)

    def test_partial_batch_is_explicit_not_a_silent_success(self):
        scan = {'status': 'completed_with_slow_regions', 'mode': 'full',
                'device_size_bytes': 8192, 'slow_regions': [
                    {'offset': n*512, 'latency_ms': 250, 'length': 512} for n in range(8)]}
        plan = plan_targeted_refresh(scan, sector=512, chunk=512, max_regions=2)
        self.assertEqual(plan['status'], 'partial_candidates_with_unresolved_data')
        self.assertEqual(len(plan['targets']), 2)
        self.assertEqual(plan['remaining_candidate_count'], 6)


class AnomalyHistoryTests(unittest.TestCase):
    def test_weak_regions_are_private_offsets_without_disk_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            identifier = 'f' * 64
            scan = {'read_error_ranges': [{'offset': 512, 'length': 512, 'error': 'user secret'}],
                    'slow_regions': [{'offset': 4096, 'length': 512, 'latency_ms': 900}]}
            result = save_hints(identifier, 8192, 512, scan, folder=root)
            self.assertEqual(result['saved_hints'], 2)
            files = list(root.glob('*.json'))
            self.assertEqual(len(files), 1)
            txt = files[0].read_text()
            self.assertNotIn('user secret', txt)
            self.assertNotIn(identifier, txt)
            self.assertEqual(len(load_hints(identifier, 8192, 512, folder=root)), 2)
            self.assertEqual(load_hints(identifier, 4096, 512, folder=root), [])
            if os.name != 'nt':
                self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)

    def test_history_follows_triage_only_when_opted_in(self):
        r = FakeReader(16*MIB)
        hints = [{'offset': 5*MIB, 'length': MIB, 'kind': 'slow'}]
        outcome = scan_reader(r, size=16*MIB, sector=512, mode='triage',
                              chunk=MIB, samples=2, history_hints=hints)
        self.assertTrue(any(o == 5*MIB for o,c in r.read_calls))
        self.assertEqual(outcome['historical_hints_used'], 1)


if __name__ == '__main__':
    unittest.main()
