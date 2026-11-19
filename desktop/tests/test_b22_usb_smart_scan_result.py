"""b22: no hardware writes, no PySide6 required."""
import json
import subprocess
import unittest
from unittest.mock import patch

from driverepair_desktop.devices import Device
from driverepair_desktop.health import health_snapshot
from driverepair_desktop.diagnostic_outcome import classify_scan_outcome
from driverepair_desktop.scan_followup import checked_ranges


class SmartBridgeFallbackTests(unittest.TestCase):
    def setUp(self):
        self.disk = Device('windows:PhysicalDrive4', r'\\.\PhysicalDrive4',
                           'Test rotational HDD', 4096*100, 512, 'usb', 'ser12345')
        self.smart = {'device': {'protocol': 'ATA'}, 'rotation_rate': 5400,
                      'smart_status': {'passed': True},
                      'ata_smart_attributes': {'table': []}}

    def test_second_sat_mode_accepted_after_invalid_primary(self):
        commands = []
        def fake_run(cmd, **kwargs):
            commands.append(cmd)
            if '-l' in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout=b'{}')
            if '-d' not in cmd:
                return subprocess.CompletedProcess(cmd, 2, stdout=b'USB bridge returned text')
            mode = cmd[cmd.index('-d')+1]
            if mode == 'sat':
                return subprocess.CompletedProcess(cmd, 2, stdout=b'Invalid response')
            if mode == 'sat,12':
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(self.smart).encode())
            raise AssertionError('Unexpected extra probing')
        with patch('driverepair_desktop.dependencies.smartctl_path', return_value='smartctl'):
            result = health_snapshot(self.disk, run=fake_run)
        self.assertEqual(result['reported_medium'], 'hdd')
        self.assertEqual(result['source'], 'smartctl_sat,12_passthrough')
        self.assertEqual(len([c for c in commands if '-l' not in c]), 3)
        logs = [c for c in commands if '-l' in c]
        self.assertEqual(len(logs), 2)
        self.assertTrue(all(c[c.index('-d')+1] == 'sat,12' for c in logs))

    def test_invalid_primary_and_all_sat_modes_stay_unknown(self):
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 2, stdout=b'non JSON')
        with patch('driverepair_desktop.dependencies.smartctl_path', return_value='smartctl'):
            with self.assertRaisesRegex(RuntimeError, 'invalid JSON'):
                health_snapshot(self.disk, run=fake_run)


class ScanResultClassificationTests(unittest.TestCase):
    def test_nonzero_scan_exit_is_actionable_not_generic_failed(self):
        result = {'status': 'completed_with_read_errors', 'read_error_chunks': 14,
                  'read_error_ranges': [{'offset': 512, 'length': 512}]}
        view = classify_scan_outcome(result, 2, 'scanquick')
        self.assertIsNotNone(view)
        self.assertIn('14 failed read requests', view.summary)
        self.assertIn('Address scan errors', view.recommendation)
        self.assertTrue(view.complete)
        self.assertNotIn('repaired', view.headline)

    def test_failed_worker_does_not_claim_scan_completed(self):
        self.assertIsNone(classify_scan_outcome({'status': 'aborted_device_or_access_error'}, 2, 'scanfull'))
        self.assertIsNone(classify_scan_outcome({'status': 'completed_with_read_errors',
                                                 'read_error_chunks': 0}, 2, 'scanquick'))
        self.assertIsNone(classify_scan_outcome({'status': 'completed_with_read_errors',
                                                 'read_error_chunks': 14}, 2, 'carequick'))
        self.assertIsNone(classify_scan_outcome({'status': 'completed_with_read_errors',
                                                 'read_error_chunks': 14}, 15, 'scanquick'))


class FollowUpBoundsTests(unittest.TestCase):
    def test_deduplicate_with_strict_limit(self):
        device = {'identity_hint':'abcd1234', 'size_bytes': 4096*10, 'sector_size': 512}
        scan = {'device': dict(device), 'device_size_bytes':device['size_bytes'],
                'logical_sector_bytes':512,
                'read_error_ranges':[{'offset':0,'length':512}, {'offset':0,'length':512},
                                     {'offset':512,'length':512}]}
        self.assertEqual(checked_ranges(scan,device,maximum=2),
                         [{'offset':0,'length':512}, {'offset':512,'length':512}])
        for limit in (0,-1,33,1.2,True):
            with self.assertRaisesRegex(ValueError,'limit'):
                checked_ranges(scan,device,maximum=limit)

if __name__ == '__main__':
    unittest.main()
