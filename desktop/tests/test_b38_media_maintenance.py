"""Unified media-maintenance planner: decision layer only, no disk I/O."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from driverepair_desktop.media_maintenance import (
    classify_media,
    outcome_goal_for_job,
    plan_media_maintenance,
)


class MediaClassificationTests(unittest.TestCase):
    def test_ssd_model_is_flash_class(self):
        device = {
            'model': 'SanDisk SDSSDH3 500G USB Device',
            'bus': 'usb', 'sector_size': 512, 'serial_suffix': '***0000',
            'identity_hint': 'aaaaaaaaaaaa',
        }
        self.assertEqual(classify_media(device), 'ssd')

    def test_reported_hdd_medium(self):
        device = {
            'model': 'ST1000LM048', 'bus': 'usb', 'sector_size': 512,
            'serial_suffix': '***0001', 'identity_hint': 'bbbbbbbbbbbb',
        }
        self.assertEqual(classify_media(device, {'reported_medium': 'hdd'}), 'hdd')

    def test_unknown_without_device(self):
        self.assertEqual(classify_media(None), 'unknown')


class OutcomeGoalMappingTests(unittest.TestCase):
    def test_jobs_map_to_outcomes(self):
        self.assertEqual(outcome_goal_for_job('rescue'), 'rescue_data')
        self.assertEqual(outcome_goal_for_job('scanquick'), 'assess_health')
        self.assertEqual(outcome_goal_for_job('carequick'), 'maintain_media')
        self.assertEqual(outcome_goal_for_job('winfsrepair'), 'make_usable')
        self.assertEqual(outcome_goal_for_job(None, 'diagnose'), 'assess_health')


class MaintenancePlanTests(unittest.TestCase):
    ssd = {
        'model': 'SanDisk SDSSDH3 500G USB Device', 'bus': 'usb',
        'sector_size': 512, 'serial_suffix': '***0000',
        'identity_hint': 'aaaaaaaaaaaa', 'id': 'windows:PhysicalDrive3',
    }
    hdd = {
        'model': 'ST1000LM048', 'bus': 'usb', 'sector_size': 512,
        'serial_suffix': '***0001', 'identity_hint': 'bbbbbbbbbbbb',
        'id': 'windows:PhysicalDrive4',
    }

    def test_ssd_prefers_filesystem_or_rescue_never_hdd_refresh(self):
        with patch('driverepair_desktop.media_maintenance.sys.platform', 'win32'):
            plan = plan_media_maintenance(self.ssd, goal='make_usable', platform='win32')
        self.assertEqual(plan.media_class, 'ssd')
        self.assertIn(plan.primary.key, {'filesystem_repair', 'rescue_image', 'inspect_readonly'})
        keys = {op.key for op in plan.operations}
        self.assertNotIn('hdd_region_refresh', keys)  # not media-relevant
        refresh = next(op for op in plan.operations if op.key == 'qualified_flash_refresh')
        self.assertFalse(refresh.enabled)

    def test_ssd_physical_refresh_stays_fail_closed_without_lab_flag(self):
        env = {k: v for k, v in os.environ.items() if k != 'DRIVEREPAIR_ALLOW_SSD_REFRESH'}
        with patch.dict(os.environ, env, clear=True):
            plan = plan_media_maintenance(self.ssd, goal='maintain_media', platform='win32')
        refresh = next(op for op in plan.operations if op.key == 'qualified_flash_refresh')
        self.assertFalse(refresh.enabled)
        self.assertTrue(refresh.writes_patient)

    def test_lab_flag_only_enables_flash_refresh_for_ssd_class(self):
        with patch.dict(os.environ, {'DRIVEREPAIR_ALLOW_SSD_REFRESH': '1'}):
            plan = plan_media_maintenance(self.ssd, goal='maintain_media', platform='win32')
        refresh = next(op for op in plan.operations if op.key == 'qualified_flash_refresh')
        self.assertTrue(refresh.enabled)
        hdd_plan = plan_media_maintenance(
            self.hdd, {'reported_medium': 'hdd', 'rotation_rate_rpm': 5400,
                       'status': 'smart_passed_limited'},
            goal='maintain_media', platform='win32')
        self.assertFalse(any(op.key == 'qualified_flash_refresh'
                             for op in hdd_plan.operations))

    def test_confirmed_hdd_can_surface_guarded_refresh_review(self):
        snapshot = {
            'status': 'smart_passed_limited', 'reported_medium': 'hdd',
            'rotation_rate_rpm': 5400,
        }
        plan = plan_media_maintenance(self.hdd, snapshot, goal='maintain_media',
                                      platform='win32')
        self.assertEqual(plan.media_class, 'hdd')
        self.assertTrue(any(op.key == 'hdd_region_refresh' and op.enabled
                            for op in plan.operations))
        self.assertFalse(any(op.key == 'intensive_pattern_cycle' and op.enabled
                             for op in plan.operations))

    def test_unidentified_hdd_does_not_enable_writes(self):
        plan = plan_media_maintenance(self.hdd, goal='maintain_media', platform='win32')
        self.assertFalse(any(op.key == 'hdd_region_refresh' and op.enabled
                             for op in plan.operations))
        self.assertIn(plan.primary.key, {
            'filesystem_repair', 'rescue_image', 'inspect_readonly', 'weak_region_reread',
        })

    def test_level_five_analogue_never_enabled(self):
        plan = plan_media_maintenance(self.hdd, {
            'status': 'smart_passed_limited', 'reported_medium': 'hdd',
            'rotation_rate_rpm': 5400,
        }, goal='maintain_media', platform='linux')
        cycle = next(op for op in plan.operations if op.key == 'intensive_pattern_cycle')
        self.assertFalse(cycle.enabled)
        self.assertEqual(cycle.spinrite_level_analogue, 5)

    def test_plan_serializes(self):
        plan = plan_media_maintenance(None, goal='assess_health')
        payload = plan.as_dict()
        self.assertEqual(payload['media_class'], 'unknown')
        self.assertEqual(payload['primary']['key'], 'inspect_readonly')
        self.assertFalse(payload['primary']['enabled'])


class CatalogCoverageTests(unittest.TestCase):
    def test_catalog_has_more_than_four_sourced_models(self):
        from driverepair_desktop.drive_model_catalog import catalog_entries
        entries = catalog_entries()
        self.assertGreaterEqual(len(entries), 8)
        for row in entries:
            self.assertTrue(row['source_url'].startswith('https://'))


if __name__ == '__main__':
    unittest.main()
