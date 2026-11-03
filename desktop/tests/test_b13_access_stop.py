"""Regression: no unknown partition can bypass locking; STOP preserves scan evidence."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from driverepair_desktop.media_refresh import _windows_lock_paths
from driverepair_desktop.stop_control import StopRequested
from driverepair_desktop import cli


class WindowsUnmappedPartitionTests(unittest.TestCase):
    def test_partition_with_no_volume_handle_refused_even_with_dismount_approval(self):
        for paths in ([], [None], ['']):
            with self.subTest(paths=paths):
                with self.assertRaisesRegex(RuntimeError, 'no accessible lockable Windows volume handle'):
                    _windows_lock_paths([{'PartitionNumber': 2, 'Type': 'Recovery',
                                          'Paths': paths}], allow_mounted=True)

    def test_unpartitioned_disk_differs_from_inaccessible_partition(self):
        self.assertEqual(_windows_lock_paths([], allow_mounted=True), [])
        with self.assertRaisesRegex(RuntimeError, r'Partition 3 \(RAW\)'):
            _windows_lock_paths([{'PartitionNumber': 3, 'Type': 'RAW', 'Paths': []}], allow_mounted=True)

    def test_gpt_msr_reserved_partition_does_not_block_lockable_ntfs(self):
        for gpt in ('{e3c9e316-0b5c-4db8-817d-f92df00215ae}',
                    'E3C9E316-0B5C-4DB8-817D-F92DF00215AE'):
            with self.subTest(gpt=gpt):
                paths = _windows_lock_paths([
                    {'PartitionNumber': 1, 'Type': 'Reserved', 'GptType': gpt, 'Paths': []},
                    {'PartitionNumber': 2, 'Type': 'Basic', 'Paths': ['E:\\']},
                ], allow_mounted=True)
                self.assertEqual(paths, ['\\\\.\\E:'])

    def test_reserved_label_alone_cannot_bypass_volume_lock(self):
        for gpt in ('', None, '{00000000-0000-0000-0000-000000000000}',
                    '{e3c9e316-0b5c-4db8-817d-f92df00215ae'):
            with self.subTest(gpt=gpt):
                with self.assertRaisesRegex(RuntimeError, 'no accessible lockable Windows volume handle'):
                    _windows_lock_paths([
                        {'PartitionNumber': 1, 'Type': 'Reserved', 'GptType': gpt, 'Paths': []},
                        {'PartitionNumber': 2, 'Type': 'Basic', 'Paths': ['E:\\']},
                    ], allow_mounted=True)

    def test_gpt_msr_with_access_path_still_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'unexpectedly exposes AccessPaths'):
            _windows_lock_paths([
                {'PartitionNumber': 1, 'Type': 'Reserved',
                 'GptType': '{e3c9e316-0b5c-4db8-817d-f92df00215ae}', 'Paths': ['E:\\']},
            ], allow_mounted=True)


class _StopAfterOneRead:
    def __init__(self, *_args, **_kwargs):
        self.calls = 0

    def check_read_boundary(self):
        self.calls += 1
        if self.calls >= 2:
            raise StopRequested('requested from Qt')


class ScanStopTests(unittest.TestCase):
    def test_standalone_image_scan_supports_cooperative_stop_and_partial_report(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'source.img')
            path.write_bytes(b'A' * (4 * 1024 * 1024))
            args = ['scan-image', '--image', str(path), '--mode', 'triage',
                    '--samples', '4', '--chunk-mib', '1',
                    '--cooperative-stop-stdin', '--json']
            out, err = io.StringIO(), io.StringIO()
            with patch.object(cli, 'StopControl', _StopAfterOneRead):
                with redirect_stdout(out), redirect_stderr(err):
                    rc = cli.run(args)
            self.assertEqual(rc, 3)
            report = json.loads(out.getvalue())
            self.assertEqual(report['status'], 'stopped_by_user')
            self.assertTrue(report['scan_incomplete'])
            self.assertFalse(report['writes_performed'])
            self.assertEqual(report['attempted_bytes'], 1024*1024)
            self.assertEqual(report['read_error_chunks'], 0)

    def test_scan_has_private_stop_option(self):
        parsed=cli.parser().parse_args(['scan', '--device', 'windows:PhysicalDrive2',
                                        '--cooperative-stop-stdin'])
        self.assertTrue(parsed.cooperative_stop_stdin)


if __name__ == '__main__':
    unittest.main()
