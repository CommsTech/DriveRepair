"""CLI module invocation regression tests.

``python -m driverepair_desktop.cli`` must behave like the real CLI instead of
silently exiting 0, which previously looked like a successful command.
"""

import io
import contextlib
import runpy
import sys
import unittest
from unittest import mock


class CliModuleEntryTests(unittest.TestCase):
    def test_module_as_main_prints_help_and_exits_zero(self):
        """``python -m driverepair_desktop.cli --help`` exits 0 after usage."""
        with mock.patch.object(sys, 'argv', ['driverepair_desktop.cli', '--help']):
            with contextlib.redirect_stdout(io.StringIO()) as fake:
                try:
                    runpy.run_module('driverepair_desktop.cli', run_name='__main__',
                                     alter_sys=True)
                except SystemExit as exc:
                    self.assertEqual(exc.code, 0, 'expected clean --help exit')
                else:
                    self.fail('module entry must raise SystemExit from run()')
        self.assertIn('usage:', fake.getvalue())

    def test_module_as_main_bad_flag_exits_two(self):
        """An unknown flag must fail loudly instead of exiting silently 0."""
        with mock.patch.object(sys, 'argv', ['driverepair_desktop.cli', '--nope']):
            with contextlib.redirect_stderr(io.StringIO()):
                try:
                    runpy.run_module('driverepair_desktop.cli', run_name='__main__',
                                     alter_sys=True)
                except SystemExit as exc:
                    self.assertEqual(exc.code, 2)
                else:
                    self.fail('unknown flag must raise SystemExit(2)')

    def test_package_entry_still_uses_cli_main(self):
        """``driverepair_desktop.__main__`` wires to cli.main exactly once."""
        module = __import__('driverepair_desktop.__main__', fromlist=['main'])
        self.assertTrue(hasattr(module, 'main'))
        self.assertEqual(module.main.__module__, 'driverepair_desktop.cli')


if __name__ == '__main__':
    unittest.main()
