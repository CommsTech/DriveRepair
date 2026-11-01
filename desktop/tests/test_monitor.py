import json
import sys
import tempfile
import unittest
from pathlib import Path
from driverepair_desktop.monitor import evaluate_snapshot, load_history, record_monitor_sample


class MonitorTests(unittest.TestCase):
    def sample(self, *, serial='known', passed=True, errors=0, media=0):
        return {'fingerprint': serial, 'size_bytes': 4096,
                'health': {'status': 'smart_passed_limited' if passed else 'unknown',
                           'nvme': {'media_errors': media},
                           'ata_selected_raw_attributes': [{'id': 197, 'raw_value': errors}]}}

    def test_first_record_is_not_certified_healthy(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td)/'history.json')
            s = self.sample()
            result = record_monitor_sample(path, fingerprint=s['fingerprint'],
                                           size_bytes=s['size_bytes'], health=s['health'])
            self.assertEqual(result['status'], 'baseline_recorded')
            self.assertEqual(len(load_history(path)), 1)

    def test_increasing_health_errors_trigger_attention(self):
        first = self.sample()
        next_sample = self.sample(errors=1, media=2)
        result = evaluate_snapshot(first, next_sample)
        self.assertEqual(result['status'], 'attention')
        self.assertTrue(any('ata.197' in x for x in result['warnings']))
        self.assertTrue(any('nvme.media_errors' in x for x in result['warnings']))

    def test_identity_mismatch_refused(self):
        with self.assertRaises(ValueError):
            evaluate_snapshot(self.sample(), self.sample(serial='other'))

    def test_unknown_health_is_warning_not_pass(self):
        r = evaluate_snapshot(self.sample(), self.sample(passed=False))
        self.assertEqual(r['status'], 'attention')
        self.assertIn('SMART health unknown or not available', r['warnings'])

    def test_monitor_history_is_private_file_and_durable(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td)/'history.json'
            for i in range(33):
                record_monitor_sample(str(file), fingerprint='a', size_bytes=1,
                                      health={'status': 'unknown', 'nvme': {'media_errors': i}})
            self.assertEqual(len(load_history(str(file))), 30)
            if sys.platform != 'win32':
                self.assertEqual(file.stat().st_mode & 0o077, 0)

if __name__ == '__main__':
    unittest.main()
