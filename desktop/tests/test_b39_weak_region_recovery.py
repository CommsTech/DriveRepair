"""Latency-aware weak-region recovery: planning and read-only execution."""
from __future__ import annotations

import unittest

from driverepair_desktop.weak_region_recovery import (
    budget_for_media,
    observe_smart_delta,
    plan_weak_region_pass,
    prioritize_ranges,
    run_weak_region_pass,
)


class PrioritizeRangesTests(unittest.TestCase):
    def test_highest_latency_first(self):
        ranges = [
            {'offset': 0, 'length': 512},
            {'offset': 1024, 'length': 512, 'latency_ms': 12},
            {'offset': 2048, 'length': 512, 'latency_ms': 900},
        ]
        ordered = prioritize_ranges(ranges, maximum=3)
        self.assertEqual([r['offset'] for r in ordered], [2048, 1024, 0])

    def test_slow_hints_fill_missing_latency(self):
        ranges = [{'offset': 4096, 'length': 512}, {'offset': 8192, 'length': 512}]
        ordered = prioritize_ranges(
            ranges,
            slow_hints=[{'offset': 8192, 'latency_ms': 500}],
            maximum=2,
        )
        self.assertEqual(ordered[0]['offset'], 8192)


class BudgetTests(unittest.TestCase):
    def test_flash_budget_is_lower_than_hdd(self):
        flash = budget_for_media('ssd')
        hdd = budget_for_media('hdd')
        self.assertLess(flash.max_reads, hdd.max_reads)
        self.assertEqual(flash.statistical_samples, 0)

    def test_aggressive_hdd_allows_statistical_samples(self):
        budget = budget_for_media('cmr', aggressive=True)
        self.assertGreaterEqual(budget.statistical_samples, 2)


class PlanAndRunTests(unittest.TestCase):
    device = {
        'identity_hint': 'abcdef123456', 'model': 'ST1000LM048',
        'bus': 'usb', 'sector_size': 512, 'size_bytes': 8192,
        'serial_suffix': '***0001',
    }
    scan = {
        'device': {
            'identity_hint': 'abcdef123456', 'model': 'ST1000LM048',
        },
        'device_size_bytes': 8192,
        'logical_sector_bytes': 512,
        'read_error_chunks': 2,
        'read_error_ranges': [
            {'offset': 0, 'length': 512},
            {'offset': 1024, 'length': 512, 'latency_ms': 400},
        ],
        'slow_regions': [{'offset': 0, 'latency_ms': 50}],
    }

    def test_plan_selects_latency_order(self):
        plan = plan_weak_region_pass(self.device, self.scan,
                                     snapshot={'reported_medium': 'hdd'})
        self.assertEqual(plan['media_class'], 'hdd')
        self.assertEqual(plan['prioritized_offsets'][0], 1024)
        self.assertEqual(plan['patient_writes'], 0)

    def test_run_never_writes_and_records_plan(self):
        class Reader:
            def read_at(self, offset, count):
                return b'Z' * count

        report = run_weak_region_pass(self.scan, self.device, Reader(),
                                      snapshot={'reported_medium': 'hdd'})
        self.assertEqual(report['patient_writes'], 0)
        self.assertIn('plan', report)
        self.assertEqual(report['scan_regions_considered'], 2)
        self.assertTrue(report['repeatably_readable_ranges'])

    def test_smart_bookend_soft_watch(self):
        before = {'status': 'ok', 'ata_selected_raw_attributes': [{'id': 197, 'raw_value': 0}]}
        after = {'status': 'ok', 'ata_selected_raw_attributes': [{'id': 197, 'raw_value': 1}]}
        delta = observe_smart_delta(before, after)
        self.assertTrue(delta['available'])
        self.assertTrue(any('197' in item for item in delta['changes']))


if __name__ == '__main__':
    unittest.main()
