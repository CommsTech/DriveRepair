import json
import plistlib
import unittest

from driverepair_desktop.devices import (
    Device, assert_windows_external_write_gate, linux_devices, macos_devices,
    select_external_device, windows_devices,
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
        # Inventory now prefers CIM/WMIC (Get-Disk often hangs after dock reseat).
        cim_payload = [
            {"Index": 0, "InterfaceType": "SCSI", "Model": "Internal", "Size": 1048576,
             "SerialNumber": "INT", "BytesPerSector": 512},
            {"Index": 2, "InterfaceType": "USB", "Model": "USB flash", "Size": 1048576,
             "SerialNumber": "USB1", "BytesPerSector": 512},
        ]
        get_disk_payload = [
            {"Number": 0, "BusType": "SATA", "IsBoot": True, "IsSystem": True, "IsOffline": False,
             "Size": 1048576, "LogicalSectorSize": 512},
            {"Number": 2, "BusType": "USB", "IsBoot": False, "IsSystem": False, "IsOffline": False,
             "FriendlyName": "USB flash", "Size": 1048576, "LogicalSectorSize": 512},
            {"Number": 3, "BusType": "USB", "IsBoot": None, "IsSystem": False, "IsOffline": False,
             "Size": 1048576, "LogicalSectorSize": 512},
        ]

        def run(cmd, timeout=None):
            joined = " ".join(cmd).lower()
            if "get-ciminstance" in joined or "win32_diskdrive" in joined:
                return json.dumps(cim_payload).encode()
            if cmd and str(cmd[0]).lower().startswith("wmic"):
                return (
                    "Node,BytesPerSector,Index,InterfaceType,Model,SerialNumber,Size\n"
                    "BOX,512,2,USB,USB flash,USB1,1048576\n"
                ).encode()
            return json.dumps(get_disk_payload).encode()

        disks = windows_devices(run)
        self.assertEqual([disk.id for disk in disks], ["windows:PhysicalDrive2"])
        self.assertEqual(disks[0].path, r"\\.\PhysicalDrive2")
        self.assertEqual(disks[0].provenance, "legacy-inventory")

    def test_select_matches_list_fingerprint_when_get_disk_size_disagrees(self):
        # USB bridges often report a different Size via Get-Disk than CIM.
        cim = [{"Index": 2, "InterfaceType": "USB", "Model": "USB flash",
                "Size": 500105249280, "SerialNumber": "USB1", "BytesPerSector": 512}]
        get_disk = [{"Number": 2, "BusType": "USB", "IsBoot": False, "IsSystem": False,
                     "IsOffline": False, "FriendlyName": "USB flash",
                     "Size": 500107862016, "LogicalSectorSize": 512, "SerialNumber": "USB1"}]

        def run(cmd, timeout=None):
            joined = " ".join(cmd).lower()
            if "get-disk" in joined:
                return json.dumps(get_disk).encode()
            if "get-ciminstance" in joined or "win32_diskdrive" in joined:
                return json.dumps(cim).encode()
            if cmd and str(cmd[0]).lower().startswith("wmic"):
                return b"Node,BytesPerSector,Index,InterfaceType,Model,SerialNumber,Size\n"
            return json.dumps(cim).encode()

        listed = windows_devices(run)
        selected = select_external_device(listed[0].id, lambda: listed)
        self.assertEqual(selected.fingerprint[:12], listed[0].fingerprint[:12])
        assert_windows_external_write_gate(selected, run)

    def test_select_uses_cim_index_filter_for_windows_physicaldrive(self):
        calls = []

        def run(cmd, timeout=None):
            joined = " ".join(cmd)
            calls.append(joined)
            if "Index=2" in joined:
                return json.dumps([{
                    "Index": 2, "InterfaceType": "USB", "Model": "USB flash",
                    "Size": 1048576, "SerialNumber": "USB1", "BytesPerSector": 512,
                }]).encode()
            raise RuntimeError("full inventory should not be required")

        from driverepair_desktop import devices as devices_mod
        original = devices_mod._run
        devices_mod._run = run
        try:
            selected = devices_mod.select_external_device("windows:PhysicalDrive2")
        finally:
            devices_mod._run = original
        self.assertEqual(selected.id, "windows:PhysicalDrive2")
        self.assertTrue(any("Index=2" in c for c in calls))

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
