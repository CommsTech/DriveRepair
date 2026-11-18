"""No live devices. Exercise guarded release policy and media-aware repair routing."""
import argparse
from unittest import TestCase, mock

from driverepair_desktop.repair_strategy import advise
from driverepair_desktop import release_policy


class RepairBetaStrategyTests(TestCase):
    def setUp(self):
        self.dev = argparse.Namespace(model='ST1000DM010', bus='usb', sector_size=512)
        self.args = argparse.Namespace(
            command='care-external', journal_backend='disk', journal='/healthy/repair-journal',
            rewrite_neighbors=False, recording='auto', ack_unknown_health=False,
            ack_media_warning=False, max_regions=16, auto_lock_volumes=True,
        )
        self.smart = {'status': 'smart_passed_limited', 'reported_medium': 'hdd',
                      'ata_selected_raw_attributes': [], 'nvme': {}, 'temperature_c': 30}

    def guarded(self, snapshot=None):
        with mock.patch.object(release_policy, 'REPAIR_BETA_GUARDED', True):
            return release_policy.check_guarded_repair_preflight(
                self.args, self.smart if snapshot is None else snapshot, self.dev)

    def test_known_hdd_can_enter_guided_repair_pipeline_not_direct_write(self):
        result = self.guarded()
        self.assertTrue(result['can_attempt_hdd_refresh'])
        self.assertEqual(result['path'], 'hdd_targeted_refresh')

    def test_no_smart_blocked_even_with_os_healthy(self):
        weak = {'status': 'windows_health_limited', 'source': 'windows_storage_healthstatus',
                'reported_medium': 'unknown'}
        with self.assertRaisesRegex(PermissionError, 'SMART|media|HealthStatus'):
            self.guarded(weak)

    def test_ssd_nand_rewrite_never_eligible(self):
        ssd = {**self.smart, 'reported_medium': 'ssd'}
        self.assertFalse(advise(bus='sata', snapshot=ssd).can_attempt_hdd_refresh)
        with self.assertRaises(PermissionError):
            self.guarded(ssd)

    def test_nvme_failing_spare_blocks_rewrite(self):
        ssd = {**self.smart, 'reported_medium': 'ssd',
               'nvme': {'available_spare': 2, 'available_spare_threshold': 10}}
        self.assertEqual(advise(bus='nvme', snapshot=ssd).path, 'rescue_replace')

    def test_critical_warning_blocks(self):
        with self.assertRaises(PermissionError):
            self.guarded({**self.smart, 'status': 'failure_reported'})

    def test_transport_error_blocks(self):
        with self.assertRaises(PermissionError):
            self.guarded({**self.smart, 'ata_selected_raw_attributes': [{'id': 199, 'raw_value': 5}]})

    def test_smart_warning_requires_its_own_ack(self):
        warning = {**self.smart, 'ata_selected_raw_attributes': [{'id': 197, 'raw_value': 2}]}
        with self.assertRaisesRegex(PermissionError, 'ack-media-warning'):
            self.guarded(warning)
        self.args.ack_media_warning = True
        self.assertTrue(self.guarded(warning)['can_attempt_hdd_refresh'])

    def test_unknown_media_stays_unknown_behind_usb(self):
        unknown = {**self.smart, 'reported_medium': 'unknown'}
        self.assertFalse(advise(bus='usb', snapshot=unknown).can_attempt_hdd_refresh)

    def test_journal_and_batch_are_mandatory(self):
        self.args.journal_backend = 'memory'
        with self.assertRaisesRegex(PermissionError, 'durable journal'):
            self.guarded()
        self.args.journal_backend = 'disk'
        self.args.max_regions = 64
        with self.assertRaisesRegex(PermissionError, '16'):
            self.guarded()

    def test_no_geometry_override_or_neighbors(self):
        self.args.rewrite_neighbors = True
        with self.assertRaisesRegex(PermissionError, 'neighboring'):
            self.guarded()
        self.args.rewrite_neighbors = False
        self.args.recording = 'cmr'
        with self.assertRaises(PermissionError):
            self.guarded()

    def test_direct_refresh_blocked_in_repair_beta(self):
        with mock.patch.object(release_policy, 'REPAIR_BETA_GUARDED', True):
            release_policy.block_public_physical_writes('care-external')
            for command in ('refresh-external', 'refresh-image', 'care-image', 'refresh-system'):
                with self.assertRaisesRegex(ValueError, 'unavailable'):
                    release_policy.block_public_physical_writes(command)

    def test_public_image_only_still_blocks_guided_write(self):
        with mock.patch.object(release_policy, 'PUBLIC_BETA_IMAGE_ONLY', True):
            with self.assertRaises(ValueError):
                release_policy.block_public_physical_writes('care-external')

    def test_thermal_stop(self):
        with self.assertRaises(PermissionError):
            self.guarded({**self.smart, 'temperature_c': 58})
