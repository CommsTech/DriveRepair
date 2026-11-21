"""Consent and report contracts for scripts/setup_host_environment.py."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


def load_setup():
    path = ROOT / 'scripts' / 'setup_host_environment.py'
    spec = importlib.util.spec_from_file_location('setup_host_environment', path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SetupHostEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.setup = load_setup()

    def test_report_is_read_only_and_marks_no_silent_install(self):
        report = self.setup.report_environment()
        self.assertTrue(report['never_silent_install'])
        self.assertIn('beginner', report['skill_paths'])
        self.assertIn('python', report)

    def test_install_actions_refuse_without_approval(self):
        with self.assertRaisesRegex(PermissionError, 'approve-install'):
            self.setup.install_desktop_qt(approved=False)
        with self.assertRaisesRegex(PermissionError, 'approve-install'):
            self.setup.install_pytest(approved=False)
        with self.assertRaisesRegex(PermissionError, 'approve-install'):
            self.setup.install_smartctl_windows(approved=False)

    def test_cli_refuses_install_without_approve_flag(self):
        code = self.setup.main(['--install-pytest', '--json'])
        self.assertEqual(code, 2)

    def test_cli_json_report_default(self):
        buf = io.StringIO()
        with mock.patch('sys.stdout', buf):
            code = self.setup.main(['--json'])
        self.assertIn(code, (0, 1))
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['actions'], [])
        self.assertTrue(payload['report']['never_silent_install'])


if __name__ == '__main__':
    unittest.main()
