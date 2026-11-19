"""SMART breadth: full attribute table, read-only logs, USB bridge types.

Fixtures are synthetic smartctl JSON. Nothing here touches a disk.
"""
import json
import subprocess
import unittest
from unittest import mock

from driverepair_desktop import dependencies
from driverepair_desktop.devices import Device
from driverepair_desktop.drive_report import render_report
from driverepair_desktop.health import health_snapshot

ATA_ATTRIBUTES = {
    "ata_smart_attributes": {"table": [
        {"id": 5, "name": "Reallocated_Sector_Ct", "value": 100, "worst": 100,
         "thresh": 10, "when_failed": "-", "raw": {"value": 0, "string": "0"}},
        {"id": 9, "name": "Power_On_Hours", "value": 92, "worst": 92,
         "thresh": 0, "when_failed": "-", "raw": {"value": 12045, "string": "12045h+00m"}},
        {"id": 194, "name": "Temperature_Celsius", "value": 61, "worst": 41,
         "thresh": 0, "when_failed": "-", "raw": {"value": 34, "string": "34 (Min/Max 20/45)"}},
        {"id": 197, "name": "Current_Pending_Sector", "value": 100, "worst": 100,
         "thresh": 0, "when_failed": "FAILING_NOW", "raw": {"value": 8, "string": "8"}},
    ]}
}


def completed(payload, code=0):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return subprocess.CompletedProcess(['smartctl'], code, stdout=body, stderr=b'')


def make_runner(*, auto, sat=None, vendor=None, selftest=None, error_log=None):
    calls = []

    def runner(cmd, **kwargs):
        calls.append(list(cmd))
        args = ' '.join(cmd)
        if '-l selftest' in args:
            return completed(selftest if selftest is not None else {'selftest': {'exit_status': 0}})
        if '-l error' in args:
            return completed(error_log if error_log is not None else {'error': {'exit_status': 0}})
        if '-d sat' in args:
            return completed(sat if sat is not None else {}, 0 if sat else 1)
        if 'sntjmicron' in args:
            return completed(vendor if vendor is not None else {}, 0 if vendor else 1)
        if 'sntasmedia' in args:
            return completed({}, 1)
        return completed(auto)

    return runner, calls


class SmartBreadthTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(dependencies, 'smartctl_path', return_value='/verified/smartctl')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.device = Device('linux:/dev/sdz', '/dev/sdz', 'ST1000LM048', 10**12, 512,
                             'usb', 'suffix0001')

    def test_full_attribute_table_is_kept(self):
        auto = {"device": {"protocol": "ATA"}, "rotation_rate": 7200,
                "smart_status": {"passed": True}, **ATA_ATTRIBUTES}
        runner, _ = make_runner(auto=auto)
        result = health_snapshot(self.device, run=runner)
        self.assertEqual(result['ata_attribute_count'], 4)
        by_id = {a['id']: a for a in result['ata_attributes']}
        self.assertEqual(by_id[194]['name'], 'Temperature_Celsius')
        self.assertEqual(by_id[194]['value'], 61)
        self.assertEqual(by_id[194]['worst'], 41)
        self.assertEqual(by_id[197]['when_failed'], 'FAILING_NOW')
        self.assertTrue(by_id[197]['failing_now'])
        # The legacy 7-counter subset must still be present for scoring.
        self.assertEqual({a['id'] for a in result['ata_selected_raw_attributes']},
                         {5, 9, 197})

    def test_self_test_and_error_logs_are_read_not_started(self):
        auto = {"device": {"protocol": "ATA"}, "rotation_rate": 7200,
                "smart_status": {"passed": True}, **ATA_ATTRIBUTES}
        selftest = {"ata_smart_self_test_log": {"standard": {
            "count": 3, "table": [
                {"type": {"string": "Short offline"}, "status": {"string": "Completed without error"},
                 "remaining_percent": 0, "lifetime_hours": 12000, "number": 1},
            ]}}}
        error_log = {"ata_smart_error_log": {"summary": {
            "count": 2, "table": [{"error_number": 2, "lifetime_hours": 11000,
                                   "status": {"string": "UNC at LBA"}}]}}}
        runner, calls = make_runner(auto=auto, selftest=selftest, error_log=error_log)
        result = health_snapshot(self.device, run=runner)
        logs = result['smart_logs']
        self.assertTrue(logs['available'])
        self.assertEqual(logs['selftest']['count'], 3)
        self.assertEqual(logs['error_log']['count'], 2)
        self.assertEqual(logs['error_log']['last'][0]['error_number'], 2)
        # Only read-only log flags; no self-test trigger flags.
        joined = ' '.join(' '.join(c) for c in calls)
        self.assertNotIn('--test', joined)
        self.assertNotIn('--smart', joined)

    def test_usb_bridge_vendor_passthrough_is_used_when_sat_fails(self):
        auto = {"device": {"protocol": "USB"}, "smart_status": {}}
        vendor = {"device": {"protocol": "ATA"}, "rotation_rate": 5400,
                  "smart_status": {"passed": True}, **ATA_ATTRIBUTES}
        runner, calls = make_runner(auto=auto, sat=None, vendor=vendor)
        result = health_snapshot(self.device, run=runner)
        self.assertEqual(result['source'], 'smartctl_sntjmicron_passthrough')
        self.assertEqual(result['rotation_rate_rpm'], 5400)
        self.assertEqual(result['ata_attribute_count'], 4)

    def test_bridge_probes_are_bounded(self):
        auto = {"device": {"protocol": "USB"}, "smart_status": {}}
        runner, calls = make_runner(auto=auto)
        health_snapshot(self.device, run=runner)
        probe_calls = [c for c in calls if '-d' in c]
        self.assertLessEqual(len(probe_calls), 4,
                             f'too many bridge probes: {len(probe_calls)}')

    def test_missing_logs_are_reported_not_invented(self):
        auto = {"device": {"protocol": "ATA"}, "rotation_rate": 7200,
                "smart_status": {"passed": True}, **ATA_ATTRIBUTES}

        def runner(cmd, **kwargs):
            if '-l' in cmd:
                raise subprocess.TimeoutExpired(cmd, 5)
            return completed(auto)

        result = health_snapshot(self.device, run=runner)
        self.assertFalse(result['smart_logs']['available'])
        self.assertIn('reason', result['smart_logs']['selftest'])

    def test_report_contains_smart_section(self):
        auto = {"device": {"protocol": "ATA"}, "rotation_rate": 7200,
                "smart_status": {"passed": True}, **ATA_ATTRIBUTES}
        runner, _ = make_runner(auto=auto)
        snapshot = health_snapshot(self.device, run=runner)
        html = render_report({'status': 'completed', 'surface_coverage_pct': 1.0,
                              'readable_bytes': 1024, 'ata_attributes': snapshot['ata_attributes'],
                              'smart_logs': snapshot['smart_logs']},
                             device={'model': 'Example', 'bus': 'usb'})
        self.assertIn('SMART evidence', html)
        self.assertIn('Temperature_Celsius', html)
        self.assertIn('not a prediction of failure', html)

    def test_report_omits_smart_section_without_evidence(self):
        html = render_report({'status': 'completed'}, device={'model': 'Example'})
        self.assertNotIn('SMART evidence', html)


if __name__ == '__main__':
    unittest.main()
