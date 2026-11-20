"""Regression tests for always-useful repair workflow with no new write permits."""
import unittest
from driverepair_desktop.repair_routes import choose_repair_route
from driverepair_desktop.repair_readiness import ui_repair_readiness


class RepairRoutesTests(unittest.TestCase):
    ssd = {'identity_hint': 'aaaaaaaaaaaa', 'model': 'SanDisk SDSSDH3 500G USB Device',
           'serial_suffix': '***0000', 'bus': 'usb', 'sector_size': 512}
    hdd = {'identity_hint': 'bbbbbbbbbbbb', 'model': 'ST1000LM048',
           'serial_suffix': '***0001', 'bus': 'usb', 'sector_size': 512}

    def test_ssd_has_usable_safe_next_step_not_hdd_rewrite(self):
        route = choose_repair_route(self.ssd)
        self.assertEqual(route.action, 'filesystem')
        self.assertIn('filesystem', route.button)
        self.assertTrue(route.patient_write_possible)
        self.assertFalse(route.hdd_region_write_candidate)
        self.assertFalse(ui_repair_readiness(self.ssd, 'carequick')[0])

    def test_unidentified_hdd_starts_with_readonly_probe(self):
        route = choose_repair_route(self.hdd)
        self.assertEqual(route.action, 'probe')
        self.assertFalse(route.patient_write_possible)

    def test_smart_failed_hdd_has_recovery_route(self):
        snapshot = {'source': 'windows_native_unverified', 'status': 'unknown',
                    'smart_unavailable_reason': 'bridge rejected command'}
        route = choose_repair_route(self.hdd, snapshot)
        self.assertEqual(route.action, 'filesystem')
        self.assertTrue(route.patient_write_possible)
        self.assertFalse(route.hdd_region_write_candidate)

    def test_confirmed_hdd_can_request_guarded_review_only(self):
        snapshot = {'status':'smart_passed_limited', 'reported_medium':'hdd',
                    'rotation_rate_rpm':5400}
        route = choose_repair_route(self.hdd, snapshot)
        self.assertEqual(route.action, 'review')
        self.assertTrue(route.patient_write_possible)
        self.assertTrue(route.hdd_region_write_candidate)
        self.assertIn('journal', route.explanation)

    def test_no_device_cannot_start(self):
        self.assertEqual(choose_repair_route(None).action, 'select')

    def test_no_health_never_becomes_smart_pass(self):
        snap = {'source': 'windows_storage_healthstatus',
                'status': 'windows_health_limited', 'reported_medium': 'unknown'}
        self.assertFalse(choose_repair_route(self.hdd, snap).hdd_region_write_candidate)

if __name__=='__main__':
    unittest.main()
