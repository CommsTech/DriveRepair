"""No live devices: safety/accuracy tests for the image-first beta remediation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from driverepair_desktop.gui_process import prepare_child_arguments
from driverepair_desktop.release_policy import block_public_physical_writes
from driverepair_desktop.scan_checkpoint import ScanCheckpoint, load
from driverepair_desktop.health import media_from_smart
from driverepair_desktop import cli


class PublicDistributionTests(unittest.TestCase):
    def test_build_policy_blocks_all_physical_write_commands_before_opening(self):
        import driverepair_desktop.release_policy as policy
        with patch.object(policy, 'PUBLIC_BETA_IMAGE_ONLY', True):
            for command in sorted(policy.IN_PLACE_WRITE_COMMANDS):
                with self.subTest(command=command):
                    with self.assertRaisesRegex(ValueError, 'unavailable'):
                        block_public_physical_writes(command)
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                block_public_physical_writes('optimize-volume', execute_optimization=True)
            for read_only in ('scan', 'rescue-external', 'rescue-image', 'probe-region',
                              'rescue-status', 'health', 'optimize-volume'):
                block_public_physical_writes(read_only)

    def test_public_package_cannot_instantiate_raw_writer(self):
        from driverepair_desktop import release_policy, media_refresh
        from driverepair_desktop.devices import Device
        device = Device('linux:/dev/no-device', '/dev/no-device', 'Unverified',
                        4096, 512, 'usb')
        with patch.object(release_policy, 'PUBLIC_BETA_IMAGE_ONLY', True):
            with patch.object(media_refresh.os, 'open', side_effect=AssertionError('raw device opened')):
                with self.assertRaisesRegex(PermissionError, 'cannot open'):
                    media_refresh.open_device_readwrite(device)
                with self.assertRaisesRegex(PermissionError, 'cannot open'):
                    media_refresh.UnixReadWriter(device)
                with self.assertRaisesRegex(PermissionError, 'cannot open'):
                    media_refresh.WindowsReadWriter(device)
                with self.assertRaisesRegex(PermissionError, 'cannot open'):
                    media_refresh.ImageReadWriter('not-a-real-image.img')

    def test_engine_gate_precedes_device_access(self):
        import driverepair_desktop.release_policy as policy
        with patch.object(policy, 'PUBLIC_BETA_IMAGE_ONLY', True):
            with patch.object(cli, 'select_external_device', side_effect=AssertionError('DEVICE OPENED')):
                self.assertEqual(cli.run(['care-external', '--device', 'no-disk',
                                           '--journal', 'not-a-real-file', '--json']), 1)

    def test_legacy_gui_passes_safe_stop_flags(self):
        for command in ('scan', 'scan-image', 'care-image', 'care-external',
                        'refresh-image', 'refresh-external', 'refresh-system'):
            args = prepare_child_arguments([command, '--device', 'unused'])
            self.assertEqual(args.count('--cooperative-stop-stdin'), 1)
            self.assertEqual(args.count('--progress-jsonl'), 1)
            self.assertEqual(prepare_child_arguments(args), args)
        self.assertNotIn('--cooperative-stop-stdin', prepare_child_arguments(['rescue-image']))

    def test_full_refresh_parser_accepts_cooperative_stop(self):
        for name in ('refresh-image', 'refresh-external', 'refresh-system'):
            label = '--image' if name == 'refresh-image' else '--device'
            parsed = cli.parser().parse_args([name, label, 'dummy', '--cooperative-stop-stdin'])
            self.assertTrue(parsed.cooperative_stop_stdin)

    def test_coarse_windows_health_is_unknown_but_warning_remains_warning(self):
        self.assertEqual(media_from_smart({'status': 'windows_health_limited'}), 'UNKNOWN')
        self.assertEqual(media_from_smart({'status': 'windows_health_warning'}), 'WARN')
        self.assertEqual(media_from_smart({'status': 'failure_reported'}), 'FAIL')


class CheckpointSafetyTests(unittest.TestCase):
    def test_stale_pending_survives_without_blocking_new_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'checkpoint.json'
            old = path.with_suffix('.json.pending')
            old.write_text('previous crash evidence')
            writer = ScanCheckpoint(path, source_token='token', size=4096, sector=512,
                                    minimum_interval=0)
            state = {'position': 1024, 'checked': 1024, 'readable': 1024,
                     'read_count': 2, 'failures': 0}
            writer.save(state, force=True)
            self.assertEqual(load(path, source_token='token', size=4096, sector=512), state)
            self.assertEqual(old.read_text(), 'previous crash evidence')
            self.assertEqual(list(Path(directory).glob('*.pending-*')), [])
            state['position'] = 2048
            writer.save(state, force=True)
            self.assertEqual(load(path, source_token='token', size=4096, sector=512)['position'], 2048)

    def test_unaligned_untrusted_checkpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'checkpoint.json'
            payload = {'schema': 1, 'source_token': 'token', 'size': 4096, 'sector': 512,
                       'state': {'position': 0, 'checked': 0, 'readable': 0,
                                 'read_count': 0, 'failures': 1,
                                 'deferred': [{'offset': 1, 'length': 512}]}}
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, 'Invalid checkpoint range'):
                load(path, source_token='token', size=4096, sector=512)


if __name__ == '__main__':
    unittest.main()
