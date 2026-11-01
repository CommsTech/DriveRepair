import json
import plistlib
import unittest

from driverepair_desktop.devices import (
    Device, linux_devices, macos_devices, select_external_device, windows_devices,
)


class DiscoveryTests(unittest.TestCase):
    def test_linux_only_external_whole_disks(self):
        payload = {"blockdevices": [
            {"path": "/dev/sda", "type": "disk", "tran": "sata", "size": "1000000", "log-sec": 512, "rm": False, "hotplug": True},
            {"path": "/dev/sdb", "type": "disk", "tran": "usb", "size": "1048576", "log-sec": 512, "rm": False, "model": "USB drive", "serial": "ABCDEFGHI"},
            {"path": "/dev/sdb1", "type": "part", "tran": "usb", "size": "1048576", "log-sec": 512, "rm": True},
            {"path": "/dev/mmcblk0", "type": "disk", "tran": None, "size": 1048576, "log-sec": 512, "rm": True},
        ]}
        disks = linux_devices(lambda args: json.dumps(payload).encode())
        self.assertEqual([disk.id for disk in disks], ["linux:/dev/sdb", "linux:/dev/mmcblk0"])
        self.assertEqual(disks[0].public()["serial_suffix"], "***FGHI")
        self.assertNotIn("ABCDEFGHI", str(disks[0].public()))

    def test_macos_requires_external_whole_disk(self):
        listed = {"AllDisksAndPartitions": [
            {"DeviceIdentifier": "disk1"}, {"DeviceIdentifier": "disk2"},
        ]}
        infos = {
            "disk1": {"DeviceIdentifier": "disk1", "Internal": True, "WholeDisk": True,
                      "TotalSize": 1048576, "DeviceBlockSize": 512},
            "disk2": {"DeviceIdentifier": "disk2", "Internal": False, "WholeDisk": True,
                      "TotalSize": 1048576, "DeviceBlockSize": 4096,
                      "MediaName": "External SSD", "Protocol": "USB"},
        }
        def run(cmd):
            if cmd[1] == "list":
                return plistlib.dumps(listed)
            return plistlib.dumps(infos[cmd[-1]])
        disks = macos_devices(run)
        self.assertEqual(len(disks), 1)
        self.assertEqual(disks[0].path, "/dev/rdisk2")
        self.assertEqual(disks[0].sector_size, 4096)

    def test_windows_filters_boot_and_bus(self):
        payload = [
            {"Number": 0, "BusType": "SATA", "IsBoot": True, "IsSystem": True, "IsOffline": False,
             "Size": 1048576, "LogicalSectorSize": 512},
            {"Number": 2, "BusType": "USB", "IsBoot": False, "IsSystem": False, "IsOffline": False,
             "FriendlyName": "USB flash", "Size": 1048576, "LogicalSectorSize": 512},
            {"Number": 3, "BusType": "USB", "IsBoot": None, "IsSystem": False, "IsOffline": False,
             "Size": 1048576, "LogicalSectorSize": 512},
        ]
        disks = windows_devices(lambda _: json.dumps(payload).encode())
        self.assertEqual([disk.id for disk in disks], ["windows:PhysicalDrive2"])
        self.assertEqual(disks[0].path, r"\\.\PhysicalDrive2")

    def test_select_requires_exact_external_identifier(self):
        d = Device("linux:/dev/sdb", "/dev/sdb", "Demo", 1048576, 512, "usb")
        self.assertEqual(select_external_device(d.id, lambda: [d]), d)
        with self.assertRaises(ValueError):
            select_external_device("linux:/dev/sda", lambda: [d])
        with self.assertRaises(ValueError):
            select_external_device(d.id, lambda: [d, d])

    def test_identity_tracks_serial_and_size(self):
        d = Device("linux:/dev/sdb", "/dev/sdb", "Demo", 1048576, 512, "usb", "abc")
        self.assertNotEqual(d.fingerprint,
                            Device(d.id, d.path, d.model, d.size_bytes, d.sector_size, d.bus, "xyz").fingerprint)

    def test_identity_ignores_usb_location_flapping(self):
        a = Device("windows:PhysicalDrive2", r"\\.\PhysicalDrive2", "SSD", 256060514304, 512,
                   "usb", "0001", location="Bus 0 Port 0")
        b = Device("windows:PhysicalDrive2", r"\\.\PhysicalDrive2", "SSD", 256060514304, 512,
                   "usb", "0001", location="Bus 0 Port 1")
        self.assertEqual(a.fingerprint, b.fingerprint)
        self.assertEqual(a.fingerprint[:12], b.fingerprint[:12])


if __name__ == "__main__":
    unittest.main()
