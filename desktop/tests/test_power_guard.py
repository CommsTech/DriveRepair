"""RAM mode policy and transactional recovery. No physical devices opened."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from driverepair_desktop.media_refresh import ImageReadWriter, refresh_media
from driverepair_desktop.power_guard import (
    PowerGuardError, VolatilePowerGuard, _nut_status, validate_ram_journal,
)


class PowerGuardTests(unittest.TestCase):
    def test_nut_on_utility_with_capacity_and_runtime(self):
        sample = 'ups.status: OL CHRG\nbattery.charge: 99\nbattery.runtime: 3600\ndriver.name: usbhid-ups\n'
        class Proc:
            stdout = sample
        with patch('subprocess.run', return_value=Proc()) as run:
            result = _nut_status('backup')
        self.assertEqual(result['power_status'], 'OL')
        self.assertEqual(result['runtime_seconds'], 3600)
        # Local-only NUT: loopback address, never a remote hostname.
        self.assertEqual(run.call_args.args[0], ['upsc', 'backup@127.0.0.1'])

    def test_nut_rejects_low_battery_and_remote(self):
        class Proc:
            stdout = 'ups.status: OB LB\nbattery.charge: 12\nbattery.runtime: 30\ndriver.name: usbhid-ups\n'
        with patch('subprocess.run', return_value=Proc()):
            with self.assertRaises(PowerGuardError):
                _nut_status('backup')
        with self.assertRaises(PowerGuardError):
            _nut_status('backup@remote')

    def test_ram_guard_caches_short_poll_interval(self):
        with (patch('driverepair_desktop.power_guard.validate_ram_journal', return_value={'filesystem': 'tmpfs'}),
              patch('driverepair_desktop.power_guard._nut_status', return_value={'status': 'OL'}) as nut):
            guard = VolatilePowerGuard('nut:ups', '/dev/shm/test', 1024, interval_seconds=60)
            guard.check()
            guard.check()
            self.assertEqual(nut.call_count, 1)

    @unittest.skipUnless(os.path.ismount('/dev/shm'), 'No RAM mount available')
    def test_tmpfs_detection_without_swap_exposure(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as directory:
            if Path('/proc/swaps').read_text().splitlines()[1:]:
                with self.assertRaises(PowerGuardError):
                    validate_ram_journal(os.path.join(directory, 'journal'), required_bytes=1024)
            else:
                result = validate_ram_journal(os.path.join(directory, 'journal'), required_bytes=1024)
                self.assertEqual(result['filesystem'], 'tmpfs')

    def test_ramdisk_inflight_bytes_survive_new_process_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            disk = os.path.join(tmp, 'image.bin')
            journal = os.path.join(tmp, 'journal')
            payload = bytes(range(256)) * 16
            Path(disk).write_bytes(payload)
            class TearWrite(ImageReadWriter):
                def write_at(self, offset, data):
                    super().write_at(offset, b'BROKEN' + data[6:])
                    raise OSError(5, 'torn write')
            media = TearWrite(disk)
            try:
                r = refresh_media(media, size=len(payload), sector=512,
                                  source_token='test', journal=journal,
                                  chunk=1024, mode='full', journal_backend='ramdisk')
            finally:
                media.close()
            self.assertEqual(r['status'], 'aborted_write_or_verify_error')
            self.assertTrue(Path(journal, 'region.bin').is_file())
            media = ImageReadWriter(disk)
            try:
                recovered = refresh_media(media, size=len(payload), sector=512,
                                          source_token='test', journal=journal,
                                          chunk=1024, mode='full',
                                          journal_backend='ramdisk', resume=True)
            finally:
                media.close()
            self.assertEqual(recovered['status'], 'completed')
            self.assertEqual(Path(disk).read_bytes(), payload)

    def test_power_loss_blocks_write_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            disk = os.path.join(tmp, 'image.bin')
            journal = os.path.join(tmp, 'journal')
            payload = b'Z' * 4096
            Path(disk).write_bytes(payload)
            media = ImageReadWriter(disk)
            try:
                with self.assertRaises(PowerGuardError):
                    refresh_media(media, size=len(payload), sector=512, source_token='test',
                                  journal=journal, chunk=1024, mode='full',
                                  journal_backend='ramdisk',
                                  pre_write_check=lambda: (_ for _ in ()).throw(PowerGuardError('battery lost')))
            finally:
                media.close()
            self.assertEqual(Path(disk).read_bytes(), payload)
            self.assertEqual(Path(journal, 'region.bin').read_bytes(), payload[:1024])

if __name__ == '__main__':
    unittest.main()
