"""Offline boot recovery preflights never access real patient drives in tests."""
import json
import sys
import unittest
from unittest.mock import patch

from driverepair_desktop.devices import linux_all_devices, linux_devices, Device
from driverepair_desktop.cli import _parse_remote_mount, run
from driverepair_desktop.monitor import evaluate_snapshot


class OfflineRecoveryTests(unittest.TestCase):
    def test_offline_internal_discovery_is_explicit(self):
        raw = {"blockdevices": [
            {"path": "/dev/sda", "type": "disk", "tran": "sata", "size": 1048576,
             "log-sec": 512, "serial": "INTERNAL123", "model": "System"},
            {"path": "/dev/sdb", "type": "disk", "tran": "usb", "size": 1048576,
             "log-sec": 512, "serial": "USB123", "model": "Dock"},
            {"path": "/dev/loop0", "type": "loop", "size": 1048576,
             "log-sec": 512},
        ]}
        run_fake = lambda cmd: json.dumps(raw).encode()
        self.assertEqual([d.id for d in linux_devices(run_fake)], ["linux:/dev/sdb"])
        self.assertEqual([d.id for d in linux_all_devices(run_fake)],
                         ["linux:/dev/sda", "linux:/dev/sdb"])

    def test_remote_mount_must_be_known_filesystem_and_nonroot(self):
        ok = {'filesystems': [{'target': '/mnt/rescue', 'source': 'nas:/data', 'fstype': 'nfs4'}]}
        self.assertTrue(_parse_remote_mount(ok, '/mnt/rescue/case'))
        self.assertFalse(_parse_remote_mount(ok, '/mnt/other'))
        self.assertFalse(_parse_remote_mount({'filesystems': [{**ok['filesystems'][0],
            'fstype': 'overlay'}]}, '/mnt/rescue'))
        self.assertFalse(_parse_remote_mount({'filesystems': [{**ok['filesystems'][0],
            'target': '/'}]}, '/mnt/rescue'))
        self.assertFalse(_parse_remote_mount({'filesystems': [{**ok['filesystems'][0],
            'source': '/dev/sda1'}]}, '/mnt/rescue'))
        self.assertFalse(_parse_remote_mount({'filesystems': []}, '/mnt/rescue'))

    def test_fingerprint_mismatch_stops_before_disk_inspection(self):
        sample = Device('linux:/dev/sda', '/dev/sda', 'System', 1048576,
                        512, 'sata', 'INTERNAL')
        with patch('driverepair_desktop.cli.select_linux_any_disk', return_value=sample), \
             patch('driverepair_desktop.cli._verify_linux_patient_not_in_use') as idle:
            self.assertEqual(run(['plan-system-recovery', '--device', sample.id,
                                  '--output', '/tmp/not-created.img',
                                  '--expect-fingerprint', 'wrongfingerp']), 1)
            idle.assert_not_called()

    def test_live_rescue_rejects_without_offline_ack(self):
        with patch('driverepair_desktop.cli.select_linux_any_disk') as selection:
            self.assertEqual(run(['rescue-system', '--device', 'linux:/dev/sda',
                                  '--output', '/tmp/not-created.img',
                                  '--expect-fingerprint', '0123456789ab', '--ack-risk']), 1)
            selection.assert_not_called()

    def test_existing_pending_sectors_alert_on_first_sample(self):
        sample = {'fingerprint': 'a', 'size_bytes': 4096,
                  'health': {'status': 'smart_passed_limited',
                             'ata_selected_raw_attributes': [{'id': 197, 'raw_value': 3}]}}
        report = evaluate_snapshot(None, sample)
        self.assertEqual(report['status'], 'attention')
        self.assertTrue(report['recommend_preserve_data_first'])
        self.assertTrue(any('ata.197' in x for x in report['warnings']))

    def test_clean_monitor_baseline_still_baseline(self):
        sample = {'fingerprint': 'a', 'size_bytes': 4096,
                  'health': {'status': 'smart_passed_limited', 'ata_selected_raw_attributes': []}}
        self.assertEqual(evaluate_snapshot(None, sample)['status'], 'baseline_recorded')


if __name__ == '__main__': unittest.main()

class OfflineRescueIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith('linux'),
                         'rescue-system is Linux live-recovery only')
    def test_system_drive_rescue_via_mocked_linux_device_reads_only(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from driverepair_desktop.scanner import ImageReader
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            patient = root/'patient.test.image'
            data = bytes(range(256))*4096
            patient.write_bytes(data)
            output = str(root/'rescued.img')
            sample = Device('linux:/dev/sda', '/dev/sda', 'Test HDD', len(data),
                            512, 'sata', 'TESTSERIAL')
            with patch('driverepair_desktop.cli.select_linux_any_disk', return_value=sample), \
                 patch('driverepair_desktop.cli._verify_linux_patient_not_in_use'), \
                 patch('driverepair_desktop.cli._separate_linux_destination'), \
                 patch('driverepair_desktop.cli.open_device_readonly',
                       side_effect=lambda d: ImageReader(str(patient))):
                result = run(['rescue-system', '--device', sample.id,
                              '--output', output, '--expect-fingerprint', sample.fingerprint[:12],
                              '--ack-risk', '--ack-offline-system', '--multi-pass', '--json'])
            self.assertEqual(result, 0)
            self.assertEqual(patient.read_bytes(), data)
            self.assertEqual(Path(output).read_bytes(), data)
            self.assertEqual(hashlib.sha256(Path(output).read_bytes()).digest(),
                             hashlib.sha256(data).digest())
            self.assertTrue(Path(output + '.rescue.json').exists())
