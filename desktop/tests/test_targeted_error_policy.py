"""Synthetic-only evidence: read failures lead to bounded checks, not blind writes."""
import contextlib
import errno
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from driverepair_desktop.guided_repair import investigate_failed_ranges, plan_targeted_refresh
from driverepair_desktop.cli import run


class FakeReader:
    def __init__(self, data, *, failed_positions=(), fail_once=False, flip_second=False):
        self.data = bytes(data)
        self.failed_positions = set(failed_positions)
        self.fail_once = fail_once
        self.flip_second = flip_second
        self.calls = 0

    def read_at(self, offset, count):
        self.calls += 1
        if any(offset <= x < offset + count for x in self.failed_positions):
            if not self.fail_once or self.calls == 1:
                raise OSError(errno.EIO, 'injected media failure')
        chunk = self.data[offset:offset + count]
        if self.flip_second and self.calls % 2 == 0:
            return bytes([chunk[0] ^ 1]) + chunk[1:]
        return chunk


class BoundedErrorTests(unittest.TestCase):
    def test_transient_media_error_yields_repeatable_candidate(self):
        reader = FakeReader(b'Q' * 2048, failed_positions={1024}, fail_once=True)
        result = investigate_failed_ranges(reader, [{'offset': 1024, 'length': 1024}], sector=512)
        self.assertEqual(result['consistent_regions'][0]['offset'], 1024)
        self.assertEqual(result['unresolved_regions'], [])
        self.assertLessEqual(result['read_calls'], 96)

    def test_permanently_unreadable_sector_is_never_candidate(self):
        reader = FakeReader(b'Q' * 2048, failed_positions={1024})
        result = investigate_failed_ranges(reader, [{'offset': 1024, 'length': 1024}], sector=512)
        self.assertIn({'offset': 1024, 'length': 512}, result['unresolved_regions'])
        self.assertEqual(result['consistent_regions'][0]['offset'], 1536)
        self.assertNotIn(1024, [r['offset'] for r in result['consistent_regions']])

    def test_disagreeing_reads_are_not_repair_data(self):
        reader = FakeReader(b'Q' * 512, flip_second=True)
        result = investigate_failed_ranges(reader, [{'offset': 0, 'length': 512}], sector=512)
        self.assertEqual(result['consistent_regions'], [])
        self.assertEqual(result['unresolved_regions'], [{'offset': 0, 'length': 512}])

    def test_budget_is_bounded_and_unread_regions_remain_unknown(self):
        reader = FakeReader(b'Q' * 8192, failed_positions={512})
        result = investigate_failed_ranges(reader, [{'offset': 0, 'length': 8192}],
                                           sector=512, max_reads=2)
        self.assertLessEqual(result['read_calls'], 2)
        self.assertTrue(result['budget_exhausted'])
        self.assertTrue(result['unresolved_regions'])

    def test_balanced_can_select_recovered_error_chunk_not_unknown_chunk(self):
        scan = {
            'status': 'completed_with_read_errors', 'mode': 'full',
            'device_size_bytes': 4096, 'read_error_chunks': 1,
            'read_error_ranges': [{'offset': 1024, 'length': 1024}],
            'slow_regions': [{'offset': 0, 'length': 1024, 'latency_ms': 300},
                             {'offset': 1024, 'length': 1024, 'latency_ms': 300}],
            'error_investigation': {
                'consistent_regions': [{'offset': 1024, 'length': 512}],
                'unresolved_regions': [{'offset': 1536, 'length': 512}],
                'budget_exhausted': False,
            },
        }
        p = plan_targeted_refresh(scan, sector=512, chunk=1024, policy='balanced')
        self.assertEqual(p['status'], 'partial_candidates_with_unresolved_data')
        self.assertEqual(p['targets'], [(0, 1024), (1024, 512)])
        self.assertNotIn((1536, 512), p['targets'])
        conservative = plan_targeted_refresh(scan, sector=512, chunk=1024, policy='preserve')
        self.assertEqual(conservative['targets'], [(0, 1024)])

    def test_unknown_error_coordinates_and_transport_warning_stay_blocked(self):
        scan = {'status': 'completed_with_read_errors', 'mode': 'full',
                'device_size_bytes': 4096, 'read_error_chunks': 1,
                'slow_regions': [{'offset': 0, 'latency_ms': 99}]}
        self.assertEqual(plan_targeted_refresh(scan, sector=512, chunk=1024)['status'], 'blocked')
        scan['read_error_ranges'] = [{'offset': 0, 'length': 1024}]
        scan['error_investigation'] = {'consistent_regions': [{'offset': 0, 'length': 1024}],
                                       'unresolved_regions': [], 'budget_exhausted': False}
        with mock.patch('driverepair_desktop.guided_repair.transport_from_smart', return_value='WARN'):
            self.assertEqual(plan_targeted_refresh(scan, sector=512, chunk=1024,
                             hardware=True, allow_unknown_health=True,
                             allow_media_warning=True)['status'], 'blocked')

    def test_care_image_bounded_retry_and_rewrite_with_no_real_device(self):
        with tempfile.TemporaryDirectory() as td:
            image = os.path.join(td, 'patient.img')
            with open(image, 'wb') as f:
                f.write(b'X' * 4096)
            scan = {'status': 'completed_with_read_errors', 'mode': 'triage',
                    'device_size_bytes': 4096, 'read_error_chunks': 1,
                    'read_error_ranges': [{'offset': 1024, 'length': 1024}],
                    'slow_regions': [], 'inconsistent_reads': [], 'repeat_probe_failures': 0}
            out = io.StringIO()
            with mock.patch('driverepair_desktop.cli.scan_reader', return_value=scan), \
                 contextlib.redirect_stdout(out):
                code = run(['care-image', '--image', image, '--journal', os.path.join(td, 'journal'),
                            '--ack-risk', '--ack-destructive', '--ack-no-backup',
                            '--ack-data-loss-risk', '--json'])
            payload = json.loads(out.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload['repair_plan']['targets'], [[1024, 1024]])
            self.assertEqual(payload['repair']['verified_bytes'], 1024)
            with open(image, 'rb') as f:
                self.assertEqual(f.read(), b'X' * 4096)


class ErrorLimitContinuationTests(unittest.TestCase):
    def test_budget_stopped_scan_can_repair_only_verified_subranges(self):
        scan = {'status': 'aborted_error_limit', 'mode': 'full',
                'device_size_bytes': 8192, 'attempted_bytes': 4096,
                'read_error_chunks': 16,
                'read_error_ranges': [{'offset': 1024, 'length': 1024}],
                'slow_regions': [{'offset': 0, 'length': 1024, 'latency_ms': 300}],
                'error_investigation': {'consistent_regions': [{'offset': 1024, 'length': 512}],
                                        'unresolved_regions': [{'offset': 1536, 'length': 512}],
                                        'budget_exhausted': False,
                                        'device_unstable': False}}
        plan = plan_targeted_refresh(scan, sector=512, chunk=1024, policy='balanced')
        self.assertEqual(plan['status'], 'partial_candidates_with_unresolved_data')
        self.assertTrue(plan['scan_incomplete'])
        self.assertEqual(plan['scanned_bytes'], 4096)
        self.assertEqual(plan['targets'], [(0, 1024), (1024, 512)])
        self.assertNotIn((1536, 512), plan['targets'])

    def test_repeat_read_mismatch_quarantined_without_blocking_other_region(self):
        scan = {'status': 'completed_with_read_errors', 'mode': 'triage',
                'device_size_bytes': 8192, 'read_error_chunks': 0,
                'read_error_ranges': [],
                'slow_regions': [{'offset': 0, 'length': 1024, 'latency_ms': 150},
                                 {'offset': 1024, 'length': 1024, 'latency_ms': 150}],
                'inconsistent_reads': [{'offset': 1024, 'length': 1024}],
                'repeat_probe_failures': 0}
        plan = plan_targeted_refresh(scan, sector=512, chunk=1024, policy='balanced')
        self.assertEqual(plan['targets'], [(0, 1024)])
        self.assertEqual(plan['status'], 'partial_candidates_with_unresolved_data')

    def test_disconnected_during_investigation_blocks_every_write(self):
        class Disconnected:
            def read_at(self, off, length):
                raise OSError(errno.ENODEV, 'unplugged')
        evidence = investigate_failed_ranges(Disconnected(), [{'offset': 0, 'length': 1024}], sector=512)
        self.assertTrue(evidence['device_unstable'])
        self.assertLessEqual(evidence['read_calls'], 1)
        scan = {'status': 'aborted_error_limit', 'mode': 'triage',
                'device_size_bytes': 8192, 'read_error_chunks': 1,
                'read_error_ranges': [{'offset': 0, 'length': 1024}],
                'slow_regions': [{'offset': 2048, 'latency_ms': 120}],
                'error_investigation': evidence}
        plan = plan_targeted_refresh(scan, sector=512, chunk=1024)
        self.assertEqual(plan['status'], 'blocked')
        self.assertEqual(plan['targets'], [])

    def test_cli_aborted_scan_enters_partial_repair_not_global_veto(self):
        with tempfile.TemporaryDirectory() as td:
            image = os.path.join(td, 'patient.img')
            with open(image, 'wb') as f:
                f.write(b'Z' * 8192)
            scan = {'status': 'aborted_error_limit', 'mode': 'full',
                    'device_size_bytes': 8192, 'attempted_bytes': 4096,
                    'read_error_chunks': 16,
                    'read_error_ranges': [{'offset': 1024, 'length': 1024}],
                    'slow_regions': [{'offset': 0, 'length': 1024, 'latency_ms': 200}],
                    'inconsistent_reads': [], 'repeat_probe_failures': 0}
            out = io.StringIO()
            with mock.patch('driverepair_desktop.cli.scan_reader', return_value=scan), \
                 contextlib.redirect_stdout(out):
                code = run(['care-image', '--image', image, '--journal', os.path.join(td, 'journal'),
                            '--mode', 'full', '--ack-risk', '--ack-destructive', '--ack-no-backup',
                            '--ack-data-loss-risk', '--json'])
            result = json.loads(out.getvalue())
            self.assertEqual(code, 2)  # partial/unsafe to call total success
            self.assertEqual(result['status'], 'partial_repair_unresolved_data')
            self.assertEqual(result['repair']['status'], 'completed')
            self.assertTrue(result['repair_plan']['scan_incomplete'])
            self.assertGreater(result['repair']['verified_bytes'], 0)
            self.assertTrue(result['repair_plan']['unresolved_data'])

    def test_health_error_is_not_proof_of_motor_failure(self):
        from driverepair_desktop.health import ScanHealthTracker
        health = ScanHealthTracker(bus='usb')
        for i in range(4):
            health.observe(latency_ms=120, median_ms=30, failed=True)
        self.assertEqual(health.media, 'WARN')
        self.assertEqual(health.mechanical, 'WATCH')
        self.assertEqual(health.transport, 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
