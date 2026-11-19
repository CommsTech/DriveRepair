"""Regression for Windows CIM-first inventory vs independent raw-write gate.

All tests are synthetic. Never open or write a physical disk in CI.
"""
from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from driverepair_desktop import cli
from driverepair_desktop.devices import Device


class WindowsWritePreflightRegression(unittest.TestCase):
    def setUp(self):
        self.patient = Device('windows:PhysicalDrive4', r'\\.\PhysicalDrive4',
                              'ST1000LM048 USB Device', 1000000000000, 512,
                              'usb', 'SERIAL-TEST', provenance='legacy-inventory')

    def test_verified_cim_inventory_may_pass_journal_check(self):
        """An independent Get-Disk gate matters, not the original finder label."""
        completed = subprocess.CompletedProcess(['powershell'], 0, b'2', b'')
        with (mock.patch.object(cli.sys, 'platform', 'win32'),
              mock.patch.object(cli, 'assert_windows_external_write_gate') as gate,
              mock.patch.object(cli.os.path, 'abspath', return_value=r'D:\journal'),
              mock.patch.object(cli.os.path, 'splitdrive', return_value=('D:', r'\journal')),
              mock.patch.object(cli.subprocess, 'run', return_value=completed) as ps):
            cli._validate_live_refresh_preflight(self.patient, r'D:\journal')
        gate.assert_called_once_with(self.patient)
        self.assertIn('Get-Partition', ps.call_args.args[0][-1])

    def test_unverified_identity_still_blocks_before_write(self):
        no_serial = Device(self.patient.id, self.patient.path, self.patient.model,
                           self.patient.size_bytes, 512, 'usb', '',
                           provenance='native-readonly-inventory')
        with (mock.patch.object(cli.sys, 'platform', 'win32'),
              mock.patch.object(cli, 'assert_windows_external_write_gate') as gate):
            with self.assertRaisesRegex(RuntimeError, 'stable hardware serial'):
                cli._validate_live_refresh_preflight(no_serial, r'D:\journal')
        gate.assert_not_called()

    def test_get_disk_denial_still_blocks_cim_disk(self):
        with (mock.patch.object(cli.sys, 'platform', 'win32'),
              mock.patch.object(cli, 'assert_windows_external_write_gate',
                                side_effect=RuntimeError('System disk or offline')),
              mock.patch.object(cli.subprocess, 'run') as ps):
            with self.assertRaisesRegex(RuntimeError, 'System disk or offline'):
                cli._validate_live_refresh_preflight(self.patient, r'D:\journal')
        ps.assert_not_called()


if __name__ == '__main__':
    unittest.main()
