import os
import stat
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from driverepair_desktop.devices import Device
from driverepair_desktop.scanner import ImageReader, UnixReader


class ReadOnlySafetyTests(unittest.TestCase):
    def test_unix_raw_device_is_opened_read_only(self):
        disk = Device("linux:/dev/sdb", "/dev/sdb", "Test", 4096, 512, "usb")
        actual_device = SimpleNamespace(st_mode=stat.S_IFBLK, st_rdev=9)
        with patch("driverepair_desktop.scanner.sys.platform", "linux"), \
                patch("driverepair_desktop.scanner.os.open", return_value=123) as opened, \
                patch("driverepair_desktop.scanner.os.fstat", return_value=actual_device), \
                patch("driverepair_desktop.scanner.os.stat", return_value=actual_device), \
                patch("driverepair_desktop.scanner.os.close") as closed:
            reader = UnixReader(disk)
            reader.close()
        flags = opened.call_args.args[1]
        self.assertEqual(flags & (os.O_WRONLY | os.O_RDWR), 0)
        closed.assert_called_once_with(123)

    def test_unix_rejects_device_identity_swap_during_open(self):
        disk = Device("linux:/dev/sdb", "/dev/sdb", "Test", 4096, 512, "usb")
        with patch("driverepair_desktop.scanner.sys.platform", "linux"), \
                patch("driverepair_desktop.scanner.os.open", return_value=123), \
                patch("driverepair_desktop.scanner.os.fstat", return_value=SimpleNamespace(st_mode=stat.S_IFBLK, st_rdev=1)), \
                patch("driverepair_desktop.scanner.os.stat", return_value=SimpleNamespace(st_rdev=2)), \
                patch("driverepair_desktop.scanner.os.close") as closed:
            with self.assertRaises(ValueError):
                UnixReader(disk)
        closed.assert_called_once_with(123)

    def test_test_image_cannot_open_raw_device(self):
        with self.assertRaises(ValueError):
            ImageReader("/dev/null")


if __name__ == "__main__":
    unittest.main()
