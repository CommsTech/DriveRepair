"""Media routing and boot-USB regression: synthetic disks only, no disk I/O."""
import unittest
from unittest.mock import patch

from driverepair_desktop.devices import Device
from driverepair_desktop.usb_flash import eligible_flash_targets, validate_target
from driverepair_desktop.drive_model_catalog import published_model_guidance
from driverepair_desktop.devices import same_readonly_patient


class MediaCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        self.usb = Device('windows:PhysicalDrive7', r'\\.\PhysicalDrive7',
                          'SMI USB DISK USB Device', 8_000_000_000, 512, 'usb', '',
                          provenance='legacy-inventory')

    def test_serialless_windows_usb_stick_is_selectable_for_flash(self):
        with patch('driverepair_desktop.usb_flash.sys.platform', 'win32'):
            self.assertEqual(eligible_flash_targets([self.usb], 1_100_000_000), [self.usb])
            with patch('driverepair_desktop.usb_flash.assert_windows_external_write_gate') as gate:
                validate_target(self.usb, 1_100_000_000,
                                expect_fingerprint=self.usb.fingerprint[:12],
                                typed_confirmation='ERASE '+self.usb.id)
                gate.assert_called_once_with(self.usb)

    def test_internal_or_undersized_serialless_disk_is_never_flash_target(self):
        internal = Device('windows:PhysicalDrive0', r'\\.\PhysicalDrive0',
                          self.usb.model, self.usb.size_bytes, 512, 'sata')
        with patch('driverepair_desktop.usb_flash.sys.platform', 'win32'):
            self.assertEqual(eligible_flash_targets([internal, self.usb], 9_000_000_000), [])
            self.assertEqual(eligible_flash_targets([internal], 1_000_000_000), [])
            with self.assertRaises(PermissionError):
                validate_target(internal, 100_000, expect_fingerprint=internal.fingerprint[:12],
                                typed_confirmation='ERASE '+internal.id)

    def test_serialless_nonwindows_flash_is_not_authorized_by_gui(self):
        with patch('driverepair_desktop.usb_flash.sys.platform', 'linux'):
            self.assertEqual(eligible_flash_targets([self.usb], 100_000_000), [])
            with self.assertRaises(PermissionError):
                validate_target(self.usb, 100_000, expect_fingerprint=self.usb.fingerprint[:12],
                                typed_confirmation='ERASE '+self.usb.id)

    def test_readonly_health_can_tolerate_serial_disappearance_not_mismatch(self):
        stable = Device(self.usb.id, self.usb.path, self.usb.model,
                        self.usb.size_bytes, self.usb.sector_size, 'usb', 'ACTUAL123')
        assert same_readonly_patient(self.usb, stable)
        assert same_readonly_patient(stable, self.usb)
        other = Device(stable.id, stable.path, stable.model,
                       stable.size_bytes, stable.sector_size, stable.bus, 'OTHER999')
        self.assertFalse(same_readonly_patient(stable, other))
        wrong_size = Device(stable.id, stable.path, stable.model,
                            stable.size_bytes - 512, stable.sector_size, stable.bus)
        self.assertFalse(same_readonly_patient(self.usb, wrong_size))

    def test_vendor_guidance_does_not_invent_hour_limit(self):
        result = published_model_guidance('ST1000LM048-2E7172')
        self.assertEqual(result['workload_tb_per_year_max_exclusive'], 55)
        self.assertIsNone(result['rated_power_on_hours'])
        self.assertIn('seagate.com', result['source_url'])
        self.assertIsNone(published_model_guidance('Random Unknown Model'))


class SeriallessWindowsWriteGateTests(unittest.TestCase):
    def setUp(self):
        self.stick = Device('windows:PhysicalDrive7', r'\\.\PhysicalDrive7', 'SMI USB DISK',
                            8_000_000_000, 512, 'usb', '', provenance='legacy-inventory')

    def test_missing_serial_requires_same_model_and_size_under_get_disk(self):
        from driverepair_desktop.devices import assert_windows_external_write_gate
        valid = Device(self.stick.id, self.stick.path, self.stick.model,
                       self.stick.size_bytes, 512, 'usb', 'GetDisk-UniqueId', provenance='Get-Disk')
        wrong = Device(self.stick.id, self.stick.path, 'DIFFERENT DRIVE',
                       self.stick.size_bytes, 512, 'usb', '', provenance='Get-Disk')
        with patch('driverepair_desktop.devices.sys.platform', 'win32'), \
             patch('driverepair_desktop.devices._windows_devices_from_get_disk', return_value=[valid]):
            assert_windows_external_write_gate(self.stick)
        with patch('driverepair_desktop.devices.sys.platform', 'win32'), \
             patch('driverepair_desktop.devices._windows_devices_from_get_disk', return_value=[wrong]):
            with self.assertRaisesRegex(RuntimeError, 'Serial-less USB model/geometry changed'):
                assert_windows_external_write_gate(self.stick)

    def test_serialless_swap_to_other_capacity_fails(self):
        from driverepair_desktop.devices import assert_windows_external_write_gate
        different = Device(self.stick.id, self.stick.path, self.stick.model,
                           16_000_000_000, 512, 'usb', '', provenance='Get-Disk')
        with patch('driverepair_desktop.devices.sys.platform', 'win32'), \
             patch('driverepair_desktop.devices._windows_devices_from_get_disk', return_value=[different]):
            with self.assertRaises(RuntimeError):
                assert_windows_external_write_gate(self.stick)

class RepairMethodMatrixTests(unittest.TestCase):
    def test_all_known_media_offer_read_verification_and_logical_repair(self):
        from driverepair_desktop.repair_routes import supported_repair_methods
        for medium in ('hdd', 'ssd', 'nvme', 'flash'):
            with self.subTest(medium=medium):
                methods = supported_repair_methods(medium, platform='win32')
                self.assertIn('scan', methods)
                self.assertIn('filesystem', methods)
                self.assertIn('rescue', methods)
                self.assertEqual('hdd_region' in methods, medium == 'hdd')
        self.assertNotIn('filesystem', supported_repair_methods('ssd', platform='linux'))
        self.assertNotIn('hdd_region', supported_repair_methods('unknown', platform='win32'))


if __name__ == '__main__':
    unittest.main()
