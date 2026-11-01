"""No-physical-I/O tests of the opt-in, offline system-drive refresh path."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

from driverepair_desktop.cli import run
from driverepair_desktop.devices import Device
from driverepair_desktop.media_refresh import ImageReadWriter, refresh_media
from pathlib import Path
import tempfile


DISK = Device('linux:/dev/sdz', '/dev/sdz', 'Test offline disk',
              8 * 1024 * 1024, 512, 'sata', 'TEST-12345', 'HCTL 0:1:0:0', 'lsblk')


class LastResortTests(unittest.TestCase):
    def setUp(self):
        if not sys.platform.startswith('linux'):
            self.skipTest('Linux offline disk feature')
        inventory = patch('driverepair_desktop.cli.linux_all_devices', return_value=[DISK])
        inventory.start()
        self.addCleanup(inventory.stop)
        self.args = [
            'refresh-system', '--device', DISK.id,
            '--confirm-identity', DISK.fingerprint[:12],
            '--journal', '/run/driverepair-test-not-created',
            '--journal-backend', 'ramdisk', '--mode', 'adaptive',
            '--power-source', 'battery',
            '--ack-risk', '--ack-destructive', '--ack-no-backup',
            '--ack-data-loss-risk', '--ack-unvalidated-hardware',
            '--ack-offline-system', '--ack-volatile-journal',
            '--after-run', 'keep', '--no-live-dashboard', '--json',
        ]

    def invoke(self, options=None):
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = run(options or self.args)
        return code, output.getvalue(), errors.getvalue()

    @patch('driverepair_desktop.cli.open_device_readwrite')
    def test_missing_offline_confirmation_never_opens_disk(self, opener):
        code, _, errors = self.invoke([x for x in self.args if x != '--ack-offline-system'])
        self.assertEqual(code, 1)
        self.assertIn('--ack-offline-system', errors)
        opener.assert_not_called()

    @patch('driverepair_desktop.cli.open_device_readwrite')
    @patch('driverepair_desktop.cli.select_linux_any_disk', return_value=DISK)
    def test_wrong_drive_confirmation_never_opens_disk(self, select, opener):
        options = list(self.args)
        options[options.index('--confirm-identity') + 1] = 'BADFINGER123'
        code, _, errors = self.invoke(options)
        self.assertEqual(code, 1)
        self.assertIn('--confirm-identity', errors)
        opener.assert_not_called()

    @patch('driverepair_desktop.cli.open_device_readwrite')
    @patch('driverepair_desktop.cli.select_linux_any_disk', return_value=DISK)
    def test_duplicate_serial_including_internal_disk_rejected(self, select, opener):
        duplicate = Device('linux:/dev/sdy', '/dev/sdy', 'Other disk',
                           DISK.size_bytes, DISK.sector_size, 'sata', DISK.serial)
        with patch('driverepair_desktop.cli.linux_all_devices', return_value=[DISK, duplicate]):
            code, _, errors = self.invoke()
        self.assertEqual(code, 1)
        self.assertIn('same hardware serial', errors)
        opener.assert_not_called()

    @patch('driverepair_desktop.cli.open_device_readwrite')
    @patch('driverepair_desktop.cli.select_linux_any_disk', return_value=DISK)
    def test_missing_volatile_ack_never_opens_disk(self, select, opener):
        options = [x for x in self.args if x != '--ack-volatile-journal']
        code, _, errors = self.invoke(options)
        self.assertEqual(code, 1)
        self.assertIn('--ack-volatile-journal', errors)
        opener.assert_not_called()

    @patch('driverepair_desktop.cli.open_device_readwrite')
    @patch('driverepair_desktop.cli.select_linux_any_disk', return_value=DISK)
    @patch('driverepair_desktop.cli.VolatilePowerGuard')
    def test_unproven_power_never_opens_disk(self, guard, select, opener):
        guard.return_value.check.side_effect = RuntimeError('Power not established')
        code, _, errors = self.invoke()
        self.assertEqual(code, 1)
        self.assertIn('Power not established', errors)
        opener.assert_not_called()

    @patch('driverepair_desktop.cli.open_device_readwrite')
    @patch('driverepair_desktop.cli.select_linux_any_disk', return_value=DISK)
    @patch('driverepair_desktop.cli.VolatilePowerGuard')
    @patch('driverepair_desktop.cli._validate_live_refresh_preflight')
    @patch('driverepair_desktop.cli.refresh_media')
    def test_safe_checks_and_routing_to_existing_transaction_engine(
        self, engine, preflight, guard, select, opener
    ):
        opener.return_value = MagicMock()
        engine.return_value = {
            'status': 'completed', 'transaction': None, 'rewritten_bytes': 4096,
            'verified_bytes': 4096,
        }
        code, stdout, errors = self.invoke()
        self.assertEqual(code, 0, errors)
        self.assertEqual(json.loads(stdout)['status'], 'completed')
        preflight.assert_called_once_with(
            DISK, '/run/driverepair-test-not-created', ramdisk=True
        )
        self.assertEqual(select.call_count, 3)  # before, after, and identity check in callback
        opener.assert_called_once_with(DISK)
        self.assertEqual(engine.call_args.kwargs['journal_backend'], 'ramdisk')
        self.assertEqual(engine.call_args.kwargs['source_token'], DISK.fingerprint)
        self.assertIsNotNone(engine.call_args.kwargs['pre_write_check'])
        opener.return_value.close.assert_called_once()

    def test_simulated_ramdisk_journal_recovers_after_torn_write_and_restart(self):
        # Regular-file simulation: not real tmpfs/patient hardware validation.
        with tempfile.TemporaryDirectory() as td:
            patient = Path(td) / 'test.img'
            data = bytes(range(256)) * 32
            patient.write_bytes(data)
            journal = str(Path(td) / 'volatile-journal')

            class TornOnce(ImageReadWriter):
                failed = False

                def write_at(self, offset, chunk):
                    if not self.failed:
                        self.failed = True
                        super().write_at(offset, b'X' * min(32, len(chunk)))
                        raise OSError(5, 'simulated partial write')
                    return super().write_at(offset, chunk)

            def job(writer, resume=False):
                try:
                    return refresh_media(writer, size=len(data), sector=512,
                                         source_token='test-stable-identity', journal=journal,
                                         journal_backend='ramdisk', mode='full', chunk=1024,
                                         resume=resume)
                finally:
                    writer.close()

            stopped = job(TornOnce(str(patient)))
            self.assertEqual(stopped['status'], 'aborted_write_or_verify_error')
            self.assertTrue((Path(journal) / 'region.bin').exists())
            self.assertNotEqual(patient.read_bytes(), data)
            finished = job(ImageReadWriter(str(patient)), resume=True)
            self.assertEqual(finished['status'], 'completed')
            self.assertEqual(patient.read_bytes(), data)

    @patch('driverepair_desktop.cli.open_device_readwrite')
    @patch('driverepair_desktop.cli.select_linux_any_disk', return_value=DISK)
    @patch('driverepair_desktop.cli.VolatilePowerGuard')
    @patch('driverepair_desktop.cli._validate_live_refresh_preflight')
    @patch('driverepair_desktop.cli.refresh_media')
    def test_reported_incomplete_run_is_not_success(
        self, engine, preflight, guard, select, opener
    ):
        engine.return_value = {'status': 'completed_with_skips_or_verify_failures',
                               'transaction': None}
        code, stdout, _ = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn('skips_or_verify_failures', stdout)


if __name__ == '__main__':
    unittest.main()
