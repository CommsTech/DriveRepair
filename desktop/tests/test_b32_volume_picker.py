"""Regression coverage for SSD repair UI and Windows exact-volume selection."""
import json
import subprocess
from pathlib import Path
import unittest
from unittest import mock

from driverepair_desktop.devices import Device
from driverepair_desktop import windows_volume_repair as wr
from driverepair_desktop.cli import parser


class RepairVolumePickerTests(unittest.TestCase):
    def setUp(self):
        self.device = Device('windows:PhysicalDrive4', r'\\.\PhysicalDrive4',
                             'SanDisk SDSSDH3 500G USB Device', 500000000000,
                             512, 'usb', 'USBSERIAL0000')
        self.record = {
            'disk_number': 4, 'disk_size': 500000000000,
            'is_boot': False, 'is_system': False, 'is_offline': False,
            'volume_letter': 'E', 'filesystem': 'NTFS', 'volume_health': 'Warning',
        }

    def test_exact_volume_and_safe_subset(self):
        rec2 = {**self.record, 'volume_letter': 'F', 'filesystem': 'exFAT'}
        other = {**self.record, 'volume_letter': 'G', 'filesystem': 'RAW'}
        result = wr.parse_repairable_volumes(json.dumps([rec2, other, self.record]).encode(),
                                             device=self.device)
        self.assertEqual([v['letter'] for v in result], ['E','F'])
        self.assertEqual(result[0]['disk_number'], 4)
        self.assertEqual(wr.parse_repairable_volumes(b'[]', device=self.device), [])

    def test_fails_closed_on_unsafe_or_mismatched_volume(self):
        for change in ({'disk_number': 2}, {'disk_size': 7777777},
                       {'is_boot': True}, {'is_system': True}, {'is_offline': True}):
            with self.subTest(change=change), self.assertRaises((RuntimeError,PermissionError)):
                wr.parse_repairable_volumes(json.dumps([{**self.record,**change}]).encode(),device=self.device)
        with self.assertRaises(RuntimeError):
            wr.parse_repairable_volumes(json.dumps([self.record,self.record]).encode(),device=self.device)
        for raw in (b'{}', b'"string"', b'not json', b'[42]'):
            with self.subTest(raw=raw),self.assertRaises(RuntimeError):
                wr.parse_repairable_volumes(raw,device=self.device)

    @mock.patch.object(wr.sys, 'platform', 'win32')
    def test_inventory_is_readonly_bounded_and_matches_disk(self):
        completed=subprocess.CompletedProcess(['powershell.exe'],0,
            json.dumps([self.record]).encode(),b'')
        run=mock.Mock(return_value=completed)
        volume=wr.inspect_windows_repairable_volumes(self.device,run=run)
        self.assertEqual(volume[0]['letter'],'E')
        cmd=run.call_args.args[0]
        self.assertEqual(cmd[0],'powershell.exe')
        self.assertIn('Get-Partition -DiskNumber 4',cmd[-1])
        self.assertIn('Get-Volume',cmd[-1])
        self.assertEqual(run.call_args.kwargs['timeout'],12)
        self.assertNotIn('chkdsk',str(cmd).lower())
        self.assertNotIn('Set-',str(cmd))

    @mock.patch.object(wr.sys,'platform','win32')
    def test_timed_out_volume_lookup_never_performs_repair(self):
        run=mock.Mock(side_effect=subprocess.TimeoutExpired(['powershell.exe'],12))
        with self.assertRaisesRegex(RuntimeError,'no repair was started'):
            wr.inspect_windows_repairable_volumes(self.device,run=run)
        self.assertEqual(run.call_count,1)

    def test_cli_has_exact_disk_volume_listing(self):
        parsed=parser().parse_args(['list-repair-volumes','--device',self.device.id,
                                    '--confirm-identity',self.device.fingerprint[:12],'--json'])
        self.assertEqual(parsed.command,'list-repair-volumes')
        self.assertEqual(parsed.confirm_identity,self.device.fingerprint[:12])

    def test_qt_repair_keeps_manual_method_and_does_not_redirect(self):
        code=(Path(__file__).resolve().parents[1]/'driverepair_desktop'/'qtgui.py').read_text(encoding='utf-8')
        self.assertIn("('Repair NTFS / exFAT / FAT volume (HDD, SSD, NVMe, USB)','winfsrepair')", code)
        self.assertNotIn('if flash is not None:', code)
        self.assertIn('Preserve the operator', code)
        self.assertIn('def repair_volumes_ready(self, child, exit_code)',code)
        self.assertIn("self.start_windows_filesystem_repair()", code)
        self.assertNotIn("elif decision['action']=='rescue':\n                self.start_job(repair_copy=True)",code)

if __name__=='__main__':
    unittest.main()
