"""Security hardening regressions raised by the 2026-11-19 specialist review.

Two LOW findings, both about trusting a resolved path instead of a bare name:
- SMART evidence must come from the resolved smartctl path, never a bare PATH
  lookup that a planted executable could satisfy.
- A repair journal must not be adopted through a symlink or inherit a
  world-readable directory mode.
"""
import os
import stat
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from driverepair_desktop import dependencies, health
from driverepair_desktop.media_refresh import JournalStore


def fake_device(path):
    return SimpleNamespace(path=path, bus='usb', model='Example Drive',
                           sector_size=512, serial_suffix='0000',
                           public=lambda: {'model': 'Example Drive', 'bus': 'usb'})


class SmartctlPathTrustTests(unittest.TestCase):
    def test_missing_smartctl_fails_closed_without_running_anything(self):
        run = mock.Mock()
        with mock.patch.object(dependencies, 'smartctl_path', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'smartctl'):
                health.health_snapshot(fake_device(r'\\.\PhysicalDrive9'), run=run)
        run.assert_not_called()

    def test_resolved_path_is_the_only_executable_used(self):
        run = mock.Mock(return_value=SimpleNamespace(stdout=b'{}', returncode=0, stderr=b''))
        with mock.patch.object(dependencies, 'smartctl_path', return_value='/verified/smartctl'):
            health.health_snapshot(fake_device('/dev/sdz'), run=run)
        self.assertEqual(run.call_args.args[0][0], '/verified/smartctl')

    def test_health_module_has_no_bare_smartctl_fallback(self):
        with open(health.__file__, encoding='utf-8') as handle:
            source = handle.read()
        self.assertNotIn("or 'smartctl'", source)


class JournalDirectorySafetyTests(unittest.TestCase):
    def test_symlinked_journal_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            real = os.path.join(td, 'real-empty')
            os.mkdir(real)
            link = os.path.join(td, 'journal-link')
            os.symlink(real, link)
            store = JournalStore(link, 'disk')
            with self.assertRaisesRegex(FileExistsError, 'symbolic link'):
                store.prepare_new()
            self.assertEqual(os.listdir(real), [], 'refused journal must stay untouched')

    @unittest.skipUnless(os.name == 'posix', 'POSIX directory modes only')
    def test_adopted_empty_directory_becomes_private(self):
        with tempfile.TemporaryDirectory() as td:
            journal = os.path.join(td, 'precreated')
            os.mkdir(journal, 0o755)
            os.chmod(journal, 0o755)
            JournalStore(journal, 'disk').prepare_new()
            mode = stat.S_IMODE(os.stat(journal).st_mode)
            self.assertEqual(mode, 0o700, f'expected 0700, got {oct(mode)}')

    def test_journal_with_leftover_artifacts_still_refuses(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, 'meta.json'), 'w', encoding='utf-8') as handle:
                handle.write('{}')
            with self.assertRaisesRegex(FileExistsError, 'already exists'):
                JournalStore(td, 'disk').prepare_new()


if __name__ == '__main__':
    unittest.main()
