"""Guardrails for the independent Windows filesystem repair workflow."""
import json
import subprocess
import unittest
from unittest import mock

from driverepair_desktop import release_policy
from driverepair_desktop import windows_volume_repair as wr
from driverepair_desktop.devices import Device
from driverepair_desktop.repair_routes import choose_repair_route
from driverepair_desktop.workstation_ui import WORKSPACES, operation_family, can_start


class VolumeRepairSafety(unittest.TestCase):
    def setUp(self):
        self.device=Device('windows:PhysicalDrive4', r'\\.\PhysicalDrive4',
                           'SanDisk SDSSDH3 500G USB Device', 500000000000, 512,
                           'usb', 'USBSERIAL0000')
        self.binding={
            'disk_number':4, 'disk_size':500000000000, 'is_boot':False,
            'is_system':False,'is_offline':False, 'volume_letter':'E',
            'filesystem':'NTFS','volume_health':'Warning'}

    def parse(self, **change):
        return wr.parse_volume_binding(json.dumps({**self.binding, **change}).encode(),
                                       device=self.device,letter='E')

    def test_requires_exact_volume_disk_relation(self):
        self.assertEqual(self.parse()['filesystem'], 'NTFS')
        for change in ({'disk_number':3}, {'disk_size':200000},
                       {'is_boot':True}, {'is_system':True},
                       {'is_offline':True}, {'volume_letter':'F'},
                       {'filesystem':'RAW'}, {'filesystem':'ReFS'}):
            with self.subTest(change=change), self.assertRaises((ValueError, PermissionError, RuntimeError)):
                self.parse(**change)

    def test_refuses_malformed_json_and_unsafe_drive_letter(self):
        with self.assertRaises(RuntimeError):
            wr.parse_volume_binding(b'{invalid',device=self.device,letter='E')
        for token in ('C','C:', 'E; rm', '/dev/sdb','Z: /f', '1'):
            with self.subTest(token=token), self.assertRaises(ValueError):
                wr._letter(token)
        self.assertEqual(wr._letter('e:'),'E')

    @mock.patch.object(wr.sys,'platform','win32')
    def test_check_never_calls_chkdsk_and_write_requires_both_acks(self):
        with (mock.patch.object(wr,'select_external_device',return_value=self.device),
              mock.patch.object(wr,'inspect_windows_volume',return_value=self.parse()),
              mock.patch.object(wr,'assert_windows_external_write_gate')):
            plan=wr.windows_filesystem_maintenance(self.device.id, 'E',
                confirm_identity=self.device.fingerprint[:12])
            self.assertEqual(plan['mode'],'read_only_plan')
            self.assertIs(plan['writes_performed'],False)
            for a,b in [(False,False),(True,False),(False,True)]:
                with self.subTest(acks=(a,b)), self.assertRaises(PermissionError):
                    wr.windows_filesystem_maintenance(self.device.id, 'E',
                        confirm_identity=self.device.fingerprint[:12],
                        execute=True,ack_backup=a,ack_write=b)

    @mock.patch.object(wr.sys,'platform','win32')
    def test_command_uses_exact_chkdsk_f_and_verification_not_claimed(self):
        fake=subprocess.CompletedProcess(['chkdsk.exe','E:','/f'],0,b'Windows repaired the filesystem')
        with (mock.patch.object(wr,'select_external_device',return_value=self.device),
              mock.patch.object(wr,'inspect_windows_volume',return_value=self.parse()),
              mock.patch.object(wr,'assert_windows_external_write_gate'),
              mock.patch.object(wr,'assert_stable_identity'),
              mock.patch.object(release_policy,'PUBLIC_BETA_IMAGE_ONLY',False)):
            run=mock.Mock(return_value=fake)
            outcome=wr.windows_filesystem_maintenance(self.device.id,'E',
                confirm_identity=self.device.fingerprint[:12],execute=True,
                ack_backup=True,ack_write=True,runner=run)
        self.assertEqual(outcome['status'],'repair_command_completed_unverified')
        self.assertEqual(run.call_args.args[0],['chkdsk.exe','E:','/f'])
        self.assertEqual(run.call_args.kwargs['stdin'],subprocess.DEVNULL)
        self.assertNotIn('/r',run.call_args.args[0])

    @mock.patch.object(wr.sys,'platform','win32')
    def test_public_beta_refuses_write_even_if_cli_called_directly(self):
        with (mock.patch.object(wr,'select_external_device',return_value=self.device),
              mock.patch.object(wr,'inspect_windows_volume',return_value=self.parse()),
              mock.patch.object(release_policy,'PUBLIC_BETA_IMAGE_ONLY',True)):
            with self.assertRaises(PermissionError):
                wr.windows_filesystem_maintenance(self.device.id,'E',
                    confirm_identity=self.device.fingerprint[:12],execute=True,
                    ack_backup=True,ack_write=True)

    def test_release_policy_allows_read_only_plan_never_public_write(self):
        with mock.patch.object(release_policy,'PUBLIC_BETA_IMAGE_ONLY',True):
            release_policy.block_public_physical_writes('repair-windows-filesystem',execute_optimization=False)
            with self.assertRaises(ValueError):
                release_policy.block_public_physical_writes('repair-windows-filesystem',execute_optimization=True)

    def test_qt_never_terminates_chkdsk_as_readonly_scan(self):
        from pathlib import Path
        qt=Path(__file__).resolve().parents[1] / 'driverepair_desktop' / 'qtgui.py'
        src=qt.read_text(encoding='utf-8')
        self.assertIn("self.stop.setEnabled(self._last_job_kind != 'winfsrepair')",src)
        self.assertIn("if self._last_job_kind == 'winfsrepair':",src)
        self.assertIn('Filesystem repair cannot be interrupted safely',src)

    def test_repair_restore_workspaces_are_distinct_and_ssd_stays_repair(self):
        self.assertEqual(operation_family('winfsrepair'),'fix')
        self.assertNotIn('restore',WORKSPACES['fix'].title.lower())
        self.assertIn('Restore',WORKSPACES['recover'].title)
        route=choose_repair_route(self.device.public())
        self.assertEqual(route.action,'filesystem')
        self.assertNotIn('image',route.button.lower())
        self.assertTrue(route.patient_write_possible)
        self.assertFalse(route.hdd_region_write_candidate)
        self.assertTrue(can_start('winfsrepair',device_selected=True,image_exists=False,
                                  running=False,public_beta=False)[0])
        self.assertFalse(can_start('winfsrepair',device_selected=True,image_exists=False,
                                   running=False,public_beta=True)[0])

if __name__=='__main__':
    unittest.main()
