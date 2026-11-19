"""No raw device access: synthetic SMART and destructive wizard readiness."""
import json
import subprocess
import unittest

from driverepair_desktop.devices import Device
from driverepair_desktop.health import health_snapshot
from driverepair_desktop.usb_flash import flash_confirmation_state


class UsbHealthRegression(unittest.TestCase):
    def setUp(self):
        from unittest import mock as _mock
        from driverepair_desktop import dependencies
        patcher = _mock.patch.object(dependencies, 'smartctl_path', return_value='smartctl')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.drive = Device('windows:PhysicalDrive3', r'\\.\PhysicalDrive3',
                            'ST1000LM048 USB bridge', 1000000000000, 512,
                            'usb', 'bridge-serial-0001')
        self.sat = {
            'device': {'protocol': 'ATA'}, 'rotation_rate': 5400,
            'smart_status': {'passed': True}, 'ata_smart_attributes': {'table': []},
        }

    def test_auto_device_open_error_can_be_followed_by_valid_sat(self):
        calls = []
        def runner(cmd, **kwargs):
            calls.append(cmd)
            if '-d' in cmd:
                return subprocess.CompletedProcess(cmd, 0,
                    stdout=json.dumps(self.sat).encode('utf8'))
            return subprocess.CompletedProcess(cmd, 2,
                stdout=b'{"smartctl":{"exit_status":2}}')
        report = health_snapshot(self.drive, run=runner)
        self.assertEqual(report['source'], 'smartctl_sat_passthrough')
        self.assertEqual(report['reported_medium'], 'hdd')
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[-1][-3:-1], ['-d', 'sat'])

    def test_auto_non_json_can_be_followed_by_valid_sat(self):
        def runner(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0 if '-d' in cmd else 2,
                stdout=json.dumps(self.sat).encode() if '-d' in cmd else b'USB error: invalid JSON')
        self.assertEqual(health_snapshot(self.drive, run=runner)['reported_medium'], 'hdd')

    def test_sat_must_return_ata_protocol_and_rotation(self):
        for invalid in ({'rotation_rate':5400,'device':{'protocol':'SCSI'}},
                        {'rotation_rate':0,'device':{'protocol':'SCSI'}},
                        {'device':{'protocol':'ATA'}}):
            def runner(cmd, **kwargs):
                payload=invalid if '-d' in cmd else {'device':{'protocol':'SCSI'}}
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload).encode())
            report=health_snapshot(self.drive,run=runner)
            self.assertEqual(report['reported_medium'], 'unknown')
            self.assertEqual(report['source'], 'smartctl_auto')

    def test_existing_smart_media_failure_is_never_downgraded(self):
        calls=[]
        def runner(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 8, stdout=b'{"smart_status":{"passed":false}}')
        report=health_snapshot(self.drive,run=runner)
        self.assertEqual(report['status'], 'failure_reported')
        self.assertEqual(len(calls), 1)

    def test_first_probe_timeout_does_not_send_more_usb_commands(self):
        calls=[]
        def runner(cmd, **kwargs):
            calls.append(cmd)
            raise subprocess.TimeoutExpired(cmd,kwargs.get('timeout',0))
        with self.assertRaisesRegex(RuntimeError,'timed out'):
            health_snapshot(self.drive,run=runner)
        self.assertEqual(len(calls), 1)


class UsbConfirmationUX(unittest.TestCase):
    def test_all_steps_required_and_clear_hint(self):
        settings=dict(device_selected=True, typed_confirmation='ERASE windows:PhysicalDrive4',
                      expected_confirmation='ERASE windows:PhysicalDrive4',
                      acknowledge_data_loss=True)
        ready,_=flash_confirmation_state(**settings)
        self.assertTrue(ready)
        for values,word in [({'device_selected':False},'Step 1'),
                            ({'typed_confirmation':'ERASE'},'Step 2'),
                            ({'acknowledge_data_loss':False},'Step 3'),
                            ({'worker_running':True},'already running')]:
            ready,reason=flash_confirmation_state(**(settings|values))
            self.assertFalse(ready)
            self.assertIn(word,reason)

    def test_typing_confirmation_does_not_implicitly_acknowledge_erasure(self):
        ready, reason=flash_confirmation_state(device_selected=True,
            typed_confirmation='ERASE windows:PhysicalDrive4',
            expected_confirmation='ERASE windows:PhysicalDrive4',
            acknowledge_data_loss=False)
        self.assertFalse(ready)
        self.assertIn('acknowledgement',reason)


if __name__=='__main__':
    unittest.main()
