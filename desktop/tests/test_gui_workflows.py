"""Qt-only UI entrypoint and child-process regression tests (never touch disks)."""
from __future__ import annotations
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from driverepair_desktop.gui_process import recovery_command, prepare_child_arguments


class ProcessEntryPointTests(unittest.TestCase):
    def test_installed_package_uses_module_execution(self):
        self.assertEqual(recovery_command(['rescue-image', '--help'],
            executable='/python', entrypoint='/usr/bin/driverepair-gui'),
            ['/python', '-m', 'driverepair_desktop', 'rescue-image', '--help'])
    def test_existing_portable_package_reenters_zipapp(self):
        with tempfile.TemporaryDirectory() as td:
            app=Path(td)/'DriveRepair.pyz'
            app.touch()
            self.assertEqual(recovery_command(['scan-image', '--help'],
                executable='/python', entrypoint=str(app)),
                ['/python',str(app),'scan-image','--help'])
    def test_cooperative_stop_is_only_sent_where_supported(self):
        for name in ('scan','scan-image','care-external','refresh-external'):
            args=prepare_child_arguments([name,'--help'])
            self.assertEqual(args.count('--cooperative-stop-stdin'),1)
        self.assertNotIn('--cooperative-stop-stdin',prepare_child_arguments(['rescue-image','--help']))


class QtOnlyArchitectureTests(unittest.TestCase):
    def test_no_tk_gui_is_packaged(self):
        package=Path(__file__).resolve().parents[1]/'driverepair_desktop'
        self.assertFalse((package/'gui.py').exists())
        metadata=(Path(__file__).resolve().parents[1]/'pyproject.toml').read_text()
        self.assertNotIn('driverepair_desktop.gui:launch', metadata)
    def test_missing_pyside6_fails_instead_of_launching_removed_tk(self):
        from driverepair_desktop import cli
        with patch('importlib.util.find_spec',return_value=None):
            with patch('driverepair_desktop.qtgui.launch',side_effect=AssertionError('Qt launched')):
                self.assertEqual(cli.run(['gui']),1)


class QtHeadlessSmokeTests(unittest.TestCase):
    def test_create_workstation_offscreen(self):
        try:
            import PySide6 # noqa
        except ImportError:
            self.skipTest('PySide6 not installed in test environment; run on Windows release host')
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        os.environ['DRIVEREPAIR_QT_SMOKE']='1'
        from driverepair_desktop.qtgui import launch
        # In smoke mode the window exits after 850 ms; no patient I/O is initiated.
        self.assertEqual(launch(),0)

if __name__=='__main__':
    unittest.main()
