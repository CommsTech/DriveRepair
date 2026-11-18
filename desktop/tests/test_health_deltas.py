from unittest import TestCase
from driverepair_desktop.health_deltas import compare_health


class SmartDeltaTests(TestCase):
    def test_unknown_is_not_a_pass(self):
        self.assertEqual(compare_health(None, None)['status'], 'unknown')
        self.assertEqual(compare_health({'status': 'smart_passed_limited'},
             {'source': 'windows_storage_healthstatus'})['status'], 'unknown')

    def test_stable_counters_are_not_a_media_certificate(self):
        snap = {'ata_selected_raw_attributes': [{'id': 5, 'raw_value': 3}]}
        result = compare_health(snap, snap)
        self.assertEqual(result['status'], 'no_new_counter_errors_observed')
        self.assertIn('NOT prove', result['notes'])

    def test_reallocated_increase_is_worsening_even_if_rewrite_verified(self):
        before = {'ata_selected_raw_attributes': [{'id': 5, 'raw_value': 1}]}
        after = {'ata_selected_raw_attributes': [{'id': 5, 'raw_value': 4}]}
        result = compare_health(before, after)
        self.assertEqual(result['status'], 'deteriorated')
        self.assertEqual(result['deltas']['reallocated_sectors'], 3)

    def test_nvme_spare_and_media_errors_detected(self):
        before = {'nvme': {'available_spare': 90, 'media_errors': 0}}
        after = {'nvme': {'available_spare': 87, 'media_errors': 2}}
        self.assertEqual(len(compare_health(before, after)['new_warnings']), 2)
