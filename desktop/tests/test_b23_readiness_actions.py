"""Actionable but fail-closed HDD readiness and USB SMART probe regressions.

No physical device access: all SMART runners are synthetic.
"""
import json
import subprocess
import unittest
from unittest import mock
from driverepair_desktop.devices import Device
from driverepair_desktop.health import health_snapshot
from driverepair_desktop.repair_readiness import readiness_next_action


class ReadinessNextActionTests(unittest.TestCase):
    device = {'identity_hint':'123456789abc','serial_suffix':'***0001','bus':'usb',
              'model':'ST1000LM048','sector_size':512}

    def test_missing_tool_routes_to_explicit_setup(self):
        out=readiness_next_action(self.device,'carequick',smartctl_available=False)
        self.assertEqual(out['action'],'setup')
        self.assertFalse(out['ready'])

    def test_available_tool_routes_to_readonly_probe(self):
        self.assertEqual(readiness_next_action(self.device,'carequick',
            smartctl_available=True)['action'],'probe')

    def test_coarse_windows_health_does_not_authorize_writes(self):
        out=readiness_next_action(self.device,'carequick',
            {'source':'windows_storage_healthstatus','status':'windows_health_limited',
             'smart_unavailable_reason':'USB bridge rejected SAT'},smartctl_available=True)
        self.assertEqual(out['action'],'probe')
        self.assertIn('USB bridge rejected SAT',out['reason'])

    def test_verified_hdd_still_requires_engine_gate(self):
        out=readiness_next_action(self.device,'carequick',
            {'status':'smart_passed_limited','reported_medium':'hdd',
             'rotation_rate_rpm':5400},smartctl_available=True)
        self.assertTrue(out['ready'])
        self.assertEqual(out['action'],'review')
        self.assertIn('engine must still',out['reason'])

    def test_ssd_and_flash_do_not_become_repairable(self):
        for medium in ('ssd','flash'):
            out=readiness_next_action(self.device,'carequick',
                {'status':'smart_passed_limited','reported_medium':medium},
                smartctl_available=True)
            self.assertFalse(out['ready'])
            self.assertEqual(out['action'],'rescue')

    def test_known_ssd_model_routes_to_rescue_not_smart_retry(self):
        """SanDisk SDSSDH3 must not keep offering SMART polls to unlock HDD repair."""
        ssd={'identity_hint':'aaaaaaaaaaaa','serial_suffix':'***ssd1','bus':'usb',
             'model':'SanDisk SDSSDH3 500G','sector_size':512}
        # No SMART snapshot yet — model family alone is enough to refuse HDD rewrite.
        out=readiness_next_action(ssd,'carequick',smartctl_available=True)
        self.assertFalse(out['ready'])
        self.assertEqual(out['action'],'rescue')
        self.assertIn('Rescue data',out['label'])
        # Windows HealthStatus fallback after a failed SMART probe must also
        # stop looping on "Check drive SMART" for known SSD SKUs.
        windows={'source':'windows_storage_healthstatus','status':'windows_health_limited',
                 'smart_unavailable_reason':'SMART probe failed (status bits 1: command line did not parse)'}
        out2=readiness_next_action(ssd,'carequick',windows,smartctl_available=True)
        self.assertEqual(out2['action'],'rescue')

    def test_missing_serial_stays_fail_closed(self):
        d={**self.device,'serial_suffix':'unavailable'}
        self.assertEqual(readiness_next_action(d,'carequick',
            smartctl_available=True)['action'],'identity')


class BridgePartialResponseTests(unittest.TestCase):
    def test_rotation_rate_in_failed_auto_query_is_not_a_smart_pass(self):
        device=Device('windows:PhysicalDrive3',r'\\.\PhysicalDrive3',
                      'ST1000LM048',1000000000000,512,'usb','serial0001')
        calls=[]
        good={'device':{'protocol':'ATA'},'rotation_rate':5400,
              'smart_status':{'passed':True}, 'ata_smart_attributes':{'table':[]}}
        def runner(cmd,**kw):
            calls.append(cmd)
            if '-d' in cmd:
                return subprocess.CompletedProcess(cmd,0,
                    stdout=json.dumps(good).encode())
            return subprocess.CompletedProcess(cmd,2,
                stdout=json.dumps({**good,'smartctl':{'exit_status':2}}).encode())
        with mock.patch('driverepair_desktop.dependencies.smartctl_path',return_value='smartctl'):
            report=health_snapshot(device,run=runner)
        self.assertEqual(report['source'],'smartctl_sat_passthrough')
        self.assertEqual(report['reported_medium'],'hdd')
        self.assertTrue(any('-d' in c and 'sat' in c for c in calls))


if __name__=='__main__':
    unittest.main()
