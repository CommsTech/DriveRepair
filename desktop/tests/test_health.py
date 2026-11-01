import json
import subprocess
import unittest
from driverepair_desktop.devices import Device
from driverepair_desktop.health import health_snapshot

class HealthTests(unittest.TestCase):
    def setUp(self):
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

if __name__ == '__main__':
    unittest.main()
