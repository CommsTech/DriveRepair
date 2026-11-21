"""Windows raw-access and native reliability fallbacks stay diagnostic-only."""
import contextlib
import io
import json
import subprocess
import unittest
from unittest import mock

from driverepair_desktop.devices import Device
from driverepair_desktop.health import media_from_smart, try_health_snapshot, windows_storage_reliability
from driverepair_desktop.repair_strategy import advise
from driverepair_desktop.windows_native import windows_access_preflight


class WindowsAccessTests(unittest.TestCase):
    device = Device('windows:PhysicalDrive3', r'\\.\PhysicalDrive3',
                    'ST1000LM048', 1000204886016, 512, 'usb', 'serial0001')

    def test_access_denial_is_actionable_and_no_write(self):
        error = PermissionError('access denied')
        error.winerror = 5
        with (mock.patch('driverepair_desktop.windows_native.sys.platform', 'win32'),
              mock.patch('driverepair_desktop.windows_native.windows_is_elevated', return_value=False)):
            report = windows_access_preflight(self.device,
                                              probe=mock.Mock(side_effect=error))
        self.assertEqual(report['status'], 'raw_access_denied')
        self.assertEqual(report['error_code'], 5)
        self.assertTrue(report['elevation_required'])
        self.assertFalse(report['writes_performed'])
        self.assertIn('Administrator', ' '.join(report['next_steps']))

    def test_read_access_does_not_become_write_authorization(self):
        with (mock.patch('driverepair_desktop.windows_native.sys.platform', 'win32'),
              mock.patch('driverepair_desktop.windows_native.windows_is_elevated', return_value=False)):
            report = windows_access_preflight(self.device,
                                              probe=lambda number: {'number': number})
        self.assertEqual(report['status'], 'read_only_access_available')
        self.assertTrue(report['elevation_required'])
        self.assertFalse(report['writes_performed'])


class WindowsReliabilityTests(unittest.TestCase):
    device = Device('windows:PhysicalDrive3', r'\\.\PhysicalDrive3',
                    'ST1000LM048', 1000204886016, 512, 'usb', 'serial0001')

    def payload(self, **overrides):
        data = {
            'DiskNumber': 3,
            'PhysicalDeviceId': '3',
            'Temperature': 32,
            'TemperatureMax': 45,
            'ReadErrorsCorrected': 0,
            'ReadErrorsTotal': 0,
            'ReadErrorsUncorrected': 0,
            'WriteErrorsCorrected': 0,
            'WriteErrorsTotal': 0,
            'WriteErrorsUncorrected': 0,
            'Wear': 0,
            'PowerOnHours': 100,
            'LoadUnloadCycleCount': 4,
            'StartStopCycleCount': 4,
        }
        data.update(overrides)
        return json.dumps(data).encode()

    def runner(self, payload):
        def run(command, **kwargs):
            self.assertEqual(command[0], 'powershell')
            self.assertIn('Get-StorageReliabilityCounter', command[-1])
            return subprocess.CompletedProcess(command, 0, stdout=payload)
        return run

    def test_reliability_counter_is_limited_not_smart_pass(self):
        with mock.patch('driverepair_desktop.health.sys.platform', 'win32'):
            report = windows_storage_reliability(self.device,
                                                 run=self.runner(self.payload()))
        self.assertEqual(report['source'], 'windows_storage_reliability')
        self.assertEqual(report['status'], 'windows_reliability_limited')
        self.assertIsNone(report['smart_status_passed'])
        self.assertEqual(media_from_smart(report), 'UNKNOWN')

    def test_counter_error_is_warning_and_blocks_refresh(self):
        with mock.patch('driverepair_desktop.health.sys.platform', 'win32'):
            report = windows_storage_reliability(
                self.device, run=self.runner(self.payload(ReadErrorsUncorrected=1)))
        self.assertEqual(report['status'], 'windows_reliability_warning')
        self.assertEqual(media_from_smart(report), 'WARN')
        advice = advise(model=self.device.model, bus=self.device.bus, snapshot=report)
        self.assertFalse(advice.can_attempt_hdd_refresh)
        self.assertIn('Rescue', advice.label)

    def test_nan_counter_is_ignored_not_crashing(self):
        """Non-finite counter values must not raise or masquerade as errors."""
        with mock.patch('driverepair_desktop.health.sys.platform', 'win32'):
            report = windows_storage_reliability(
                self.device,
                run=self.runner(self.payload(ReadErrorsCorrected=float('nan'),
                                             Temperature=float('nan'))))
        self.assertEqual(report['status'], 'windows_reliability_limited')
        self.assertEqual(media_from_smart(report), 'UNKNOWN')
        self.assertNotIn('ReadErrorsCorrected',
                         report['windows_storage_reliability']['counters'])
        self.assertNotIn('Temperature',
                         report['windows_storage_reliability']['counters'])

    def test_merged_snapshot_warning_routes_to_rescue(self):
        """A warning supplement over a weak snapshot must keep rescue routing."""
        base = {'status': 'unknown', 'device': self.device.public()}
        from driverepair_desktop.health import supplement_windows_reliability
        with mock.patch('driverepair_desktop.health.sys.platform', 'win32'):
            merged = supplement_windows_reliability(
                self.device, base,
                run=self.runner(self.payload(ReadErrorsUncorrected=7)))
        self.assertEqual(merged['status'], 'windows_reliability_warning')
        advice = advise(model=self.device.model, bus=self.device.bus, snapshot=merged)
        self.assertFalse(advice.can_attempt_hdd_refresh)
        self.assertIn('Rescue', advice.label)

    def test_counter_identity_mismatch_stays_unavailable(self):
        with mock.patch('driverepair_desktop.health.sys.platform', 'win32'):
            report = windows_storage_reliability(
                self.device, run=self.runner(self.payload(PhysicalDeviceId='4')))
        self.assertIsNone(report)

    def test_fallback_keeps_coarse_health_distinct(self):
        health_payload = json.dumps({
            'disk_health': 'Healthy', 'disk_operational': 'Online',
            'physical_health': 'Healthy', 'physical_operational': 'OK',
        }).encode()
        reliability_payload = self.payload()

        def run(command, **kwargs):
            script = command[-1]
            if 'Get-StorageReliabilityCounter' in script:
                return subprocess.CompletedProcess(command, 0, stdout=reliability_payload)
            return subprocess.CompletedProcess(command, 0, stdout=health_payload)

        with (mock.patch('driverepair_desktop.health.sys.platform', 'win32'),
              mock.patch('driverepair_desktop.dependencies.smartctl_path', return_value=None),
              mock.patch('driverepair_desktop.native_media.windows_native_snapshot', return_value=None),
              mock.patch('driverepair_desktop.ata_identity.windows_ata_snapshot', return_value=None)):
            snapshot = try_health_snapshot(self.device, run=run)
        self.assertEqual(snapshot['source'], 'windows_storage_healthstatus')
        self.assertEqual(snapshot['status'], 'windows_health_limited')
        self.assertIn('windows_storage_reliability', snapshot)
        self.assertNotEqual(snapshot['status'], 'smart_passed_limited')


class WindowsScanGateTests(unittest.TestCase):
    def test_scan_returns_structured_block_before_reader_open(self):
        from driverepair_desktop import cli
        device = Device('windows:PhysicalDrive3', r'\\.\PhysicalDrive3',
                        'ST1000LM048', 1000204886016, 512, 'usb', 'serial0001')
        blocked = {
            'operation': 'windows_access_preflight', 'device': device.public(),
            'status': 'raw_access_denied', 'error_code': 5,
            'error': 'WinError 5 (ERROR_ACCESS_DENIED)',
            'writes_performed': False,
        }
        out = io.StringIO()
        with (mock.patch.object(cli.sys, 'platform', 'win32'),
              mock.patch.object(cli, 'select_external_device', return_value=device),
              mock.patch('driverepair_desktop.windows_native.windows_access_preflight', return_value=blocked),
              mock.patch.object(cli, 'open_device_readonly') as reader,
              contextlib.redirect_stdout(out)):
            code = cli.run(['scan', '--device', device.id, '--mode', 'triage', '--json'])
        self.assertEqual(code, 2)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload['status'], 'blocked_windows_raw_access')
        self.assertFalse(payload['scan_performed'])
        self.assertFalse(payload['writes_performed'])
        reader.assert_not_called()


if __name__ == '__main__':
    unittest.main()
