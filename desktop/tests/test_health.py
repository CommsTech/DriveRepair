import json
import subprocess
import unittest
from unittest import mock
from driverepair_desktop.devices import Device
from driverepair_desktop.health import health_snapshot

class HealthTests(unittest.TestCase):
    def setUp(self):
        # Resolution is tested separately; these cases exercise parsing with a
        # mocked runner, so pin a resolved path instead of relying on a real
        # smartctl installation.
        from driverepair_desktop import dependencies
        patcher = mock.patch.object(dependencies, 'smartctl_path', return_value='smartctl')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.device = Device('linux:/dev/sdx', '/dev/sdx', 'USB', 4096, 512, 'usb', 'secrets')

    def test_smart_no_data_not_healthy(self):
        def runner(*args, **kw):
            return subprocess.CompletedProcess(args[0], 0, stdout=b'{}')
        result = health_snapshot(self.device, run=runner)
        self.assertEqual(result['status'], 'unknown')
        self.assertNotIn('secrets', json.dumps(result))

    def test_failed_status_overrides_passed(self):
        def runner(*args, **kw):
            return subprocess.CompletedProcess(args[0], 8,
                stdout=json.dumps({'smart_status': {'passed': True}}).encode())
        result = health_snapshot(self.device, run=runner)
        self.assertEqual(result['status'], 'failure_reported')

    def test_command_failure_is_not_passed(self):
        def runner(*args, **kw):
            return subprocess.CompletedProcess(args[0], 2, stdout=b'{}')
        with self.assertRaises(RuntimeError):
            health_snapshot(self.device, run=runner)

    def test_nvme_fields_extracted(self):
        def runner(*args, **kw):
            return subprocess.CompletedProcess(args[0], 0,
                stdout=json.dumps({'smart_status': {'passed': True},
                'nvme_smart_health_information_log': {'percentage_used': 15, 'media_errors': 2}}).encode())
        result = health_snapshot(self.device, run=runner)
        self.assertEqual(result['nvme']['percentage_used'], 15)
        self.assertEqual(result['nvme']['media_errors'], 2)
        self.assertEqual(result['status'], 'smart_passed_limited')

    def test_usb_sat_passthrough_identifies_rotational_hdd(self):
        commands=[]
        def runner(cmd, **kw):
            commands.append(cmd)
            if '-d' in cmd:
                return subprocess.CompletedProcess(cmd,0,stdout=json.dumps({
                    'rotation_rate':5400, 'smart_status':{'passed':True},
                    'device':{'protocol':'ATA'}, 'ata_smart_attributes':{'table':[]},
                }).encode())
            return subprocess.CompletedProcess(cmd,0,stdout=json.dumps({
                'device':{'protocol':'SCSI'},'smart_status':{'passed':True},
            }).encode())
        snapshot=health_snapshot(self.device,run=runner)
        self.assertEqual(snapshot['reported_medium'],'hdd')
        self.assertEqual(snapshot['rotation_rate_rpm'],5400)
        self.assertEqual(snapshot['source'],'smartctl_sat_passthrough')
        self.assertIn('-d',commands[-1])

    def test_sat_fallback_does_not_fabricate_rotational_evidence(self):
        def runner(cmd, **kw):
            if '-d' in cmd:
                return subprocess.CompletedProcess(cmd,2,stdout=b'{}')
            return subprocess.CompletedProcess(cmd,0,stdout=b'{"smart_status":{"passed":true}}')
        snapshot=health_snapshot(self.device,run=runner)
        self.assertEqual(snapshot['reported_medium'],'unknown')
        self.assertEqual(snapshot['source'],'smartctl_auto')

    def test_sat_fallback_never_downgrades_critical_warning(self):
        calls=[]
        def runner(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd,8,stdout=b'{"smart_status":{"passed":false}}')
        snapshot=health_snapshot(self.device,run=runner)
        self.assertEqual(snapshot['status'],'failure_reported')
        self.assertEqual(len(calls),1)

    def test_sat_does_not_override_known_nvme(self):
        commands=[]
        def runner(cmd, **kw):
            commands.append(cmd)
            return subprocess.CompletedProcess(cmd,0,stdout=b'{"device":{"protocol":"NVMe"},"smart_status":{"passed":true}}')
        snapshot=health_snapshot(self.device,run=runner)
        self.assertEqual(snapshot['reported_medium'],'ssd')
        self.assertEqual(len(commands),1)

    def test_scan_health_tracker_latency_and_readiness(self):
        from driverepair_desktop.health import ScanHealthTracker
        tracker = ScanHealthTracker(bus='usb', smart=None)
        self.assertEqual(tracker.media, 'UNKNOWN')
        view = tracker.observe(latency_ms=12.0, median_ms=10.0, failed=False)
        self.assertEqual(view['mechanical'], 'OK')
        self.assertIsNone(tracker.repair_readiness()['smart_status'])
        self.assertIn('media health unknown', ' '.join(tracker.repair_readiness()['blockers']))
        # Build enough OK samples for mechanical baseline while media still blocks repair.
        for _ in range(20):
            tracker.observe(latency_ms=11.0, median_ms=10.0, failed=False)
        readiness = tracker.repair_readiness()
        self.assertEqual(readiness['status'], 'blocked')
        self.assertTrue(any('media health unknown' in b for b in readiness['blockers']))
        slow = tracker.observe(latency_ms=200.0, median_ms=10.0, failed=False)
        self.assertEqual(slow['mechanical'], 'WATCH')

    def test_windows_health_fallback_maps_healthy(self):
        from driverepair_desktop.health import try_health_snapshot, media_from_smart
        device = Device('windows:PhysicalDrive2', r'\\.\PhysicalDrive2', 'Seagate', 1000, 512, 'usb')

        def runner(cmd, **kw):
            # Force SMART path miss even when smartctl.exe exists on PATH/Program Files.
            if cmd and (str(cmd[0]).lower().endswith('smartctl')
                        or str(cmd[0]).lower().endswith('smartctl.exe')
                        or cmd[0] == 'smartctl'):
                raise FileNotFoundError('smartctl')
            payload = json.dumps({
                'disk_health': 'Healthy',
                'disk_operational': 'Online',
                'physical_health': 'Healthy',
                'physical_operational': 'OK',
            }).encode()
            return subprocess.CompletedProcess(cmd, 0, stdout=payload)

        with mock.patch('driverepair_desktop.health.sys.platform', 'win32'):
            with mock.patch('driverepair_desktop.dependencies.smartctl_path', return_value=None):
                snap = try_health_snapshot(device, run=runner)
        self.assertIsNotNone(snap)
        self.assertEqual(snap['status'], 'windows_health_limited')
        self.assertEqual(media_from_smart(snap), 'UNKNOWN')
        self.assertEqual(snap['source'], 'windows_storage_healthstatus')

if __name__ == '__main__':
    unittest.main()
