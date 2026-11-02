import unittest
from types import SimpleNamespace
from unittest import mock

from driverepair_desktop import dependencies


class DependencyTests(unittest.TestCase):
    def test_which_status_never_calls_installer(self):
        # Mock both PATH lookup and Windows Program Files discovery so a
        # developer machine with smartmontools installed still exercises the
        # missing-tool branch (and never calls an installer).
        with mock.patch.object(dependencies.shutil, 'which', return_value=None):
            with mock.patch.object(dependencies, 'smartctl_path', return_value=None):
                state = dependencies.detect()
        self.assertFalse(state['smart_health_available'])
        self.assertIn('UNKNOWN', state['warning'])

    def test_windows_package_install_requires_explicit_approval(self):
        with mock.patch.object(dependencies.sys, 'platform', 'win32'):
            with self.assertRaises(PermissionError):
                dependencies.install_smartctl_windows(approved=False)

    def test_exact_package_id_and_no_shell_when_approved(self):
        called = []
        def fake_run(cmd, **kwargs):
            called.append((cmd, kwargs))
            return SimpleNamespace(returncode=0)
        with mock.patch.object(dependencies.sys, 'platform', 'win32'):
            result = dependencies.install_smartctl_windows(approved=True,
                    run=fake_run, which=lambda name: '/bin/winget')
        self.assertEqual(result['status'], 'installer_completed')
        self.assertIn('smartmontools.smartmontools', called[0][0])
        self.assertNotIn('shell', called[0][1])
        self.assertGreater(called[0][1]['timeout'], 0)


if __name__ == '__main__':
    unittest.main()
