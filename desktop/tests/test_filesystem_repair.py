import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import subprocess

from driverepair_desktop.filesystem_repair import check_ext_image, repair_ext_image


class FilesystemRepairTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.src = self.root / 'ext4.img'
        self.target = self.root / 'fixed.img'
        data = bytearray(8192)
        data[1080:1082] = b'\x53\xef'
        self.src.write_bytes(data)

    @patch('driverepair_desktop.filesystem_repair.shutil.which', return_value='/usr/bin/e2fsck')
    def test_readonly_check_invokes_e2fsck_n(self, which):
        def fake_run(command, **kwargs):
            self.assertEqual(command[:3], ['/usr/bin/e2fsck', '-f', '-n'])
            return subprocess.CompletedProcess(command, 0, b'Filesystem clean')
        with patch('driverepair_desktop.filesystem_repair.subprocess.run', side_effect=fake_run):
            result = check_ext_image(str(self.src))
        self.assertEqual(result['status'], 'clean')
        self.assertFalse(self.target.exists())

    def test_explicit_ack_required(self):
        with self.assertRaisesRegex(ValueError, 'approved'):
            repair_ext_image(str(self.src), str(self.target))
        self.assertFalse(self.target.exists())

    @patch('driverepair_desktop.filesystem_repair.shutil.which', return_value='/usr/bin/e2fsck')
    def test_repair_only_mutates_clone(self, which):
        original = self.src.read_bytes()
        def fake_run(command, **kwargs):
            self.assertEqual(command[:3], ['/usr/bin/e2fsck', '-f', '-y'])
            self.assertEqual(command[3], str(self.target))
            with open(command[3], 'r+b') as f:
                f.seek(4000)
                f.write(b'FIXED')
            return subprocess.CompletedProcess(command, 1)
        with patch('driverepair_desktop.filesystem_repair.subprocess.run', side_effect=fake_run):
            result = repair_ext_image(str(self.src), str(self.target), ack_repair=True)
        self.assertEqual(result['status'], 'corrected')
        self.assertEqual(self.src.read_bytes(), original)
        self.assertEqual(self.target.read_bytes()[4000:4005], b'FIXED')
        self.assertTrue(Path(str(self.target) + '.repair.json').exists())
        self.assertTrue(Path(str(self.target) + '.repair.log').exists())

    def test_invalid_superblock_refuses(self):
        self.src.write_bytes(b'bad' * 2000)
        with self.assertRaises(ValueError):
            repair_ext_image(str(self.src), str(self.target), ack_repair=True)
        self.assertFalse(self.target.exists())

    @patch('driverepair_desktop.filesystem_repair.shutil.which', return_value='/usr/bin/e2fsck')
    def test_existing_output_preserved(self, which):
        self.target.write_bytes(b'important')
        with self.assertRaises(FileExistsError):
            repair_ext_image(str(self.src), str(self.target), ack_repair=True)
        self.assertEqual(self.target.read_bytes(), b'important')

    @patch('driverepair_desktop.filesystem_repair.shutil.which', return_value=None)
    def test_tool_missing_blocks_repair(self, which):
        with self.assertRaises(RuntimeError):
            repair_ext_image(str(self.src), str(self.target), ack_repair=True)
        self.assertFalse(self.target.exists())

if __name__ == '__main__':
    unittest.main()
