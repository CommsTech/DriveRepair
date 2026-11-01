import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from driverepair_desktop.archive_recovery import salvage_zip

class ArchiveRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = os.path.join(self.temp.name, 'source.zip')
        self.target = os.path.join(self.temp.name, 'salvaged')

    def test_recovers_valid_members_and_flattens_paths(self):
        with zipfile.ZipFile(self.source, 'w') as zf:
            zf.writestr('../../evil.txt', b'hello')
            zf.writestr('safe/subdir/data.bin', b'working')
        result = salvage_zip(self.source, self.target)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['recovered_count'], 2)
        self.assertFalse(os.path.exists(os.path.join(self.temp.name, 'evil.txt')))
        self.assertEqual(sorted(os.listdir(self.target)), ['00001_evil.txt', '00002_data.bin'])

    def test_bad_member_does_not_erase_good_recovery(self):
        with zipfile.ZipFile(self.source, 'w', compression=zipfile.ZIP_STORED) as zf:
            zf.writestr('valid.txt', b'GOODGOODGOODGOOD')
            zf.writestr('broken.txt', b'UNIQUE_BAD_BLOCK_12345')
        b = bytearray(Path(self.source).read_bytes())
        where = b.index(b'UNIQUE_BAD_BLOCK_12345')
        b[where] ^= 0x7f
        with open(self.source, 'wb') as f:
            f.write(b)
        result = salvage_zip(self.source, self.target)
        self.assertEqual(result['status'], 'partial_archive_recovery')
        self.assertEqual(result['recovered_count'], 1)
        self.assertEqual(os.listdir(self.target), ['00001_valid.txt'])

    def test_does_not_overwrite_destination(self):
        with zipfile.ZipFile(self.source, 'w') as zf:
            zf.writestr('good', 'okay')
        os.mkdir(self.target)
        with self.assertRaises(FileExistsError):
            salvage_zip(self.source, self.target)

    def test_limit_skips_member(self):
        with zipfile.ZipFile(self.source, 'w') as zf:
            zf.writestr('large', b'Z' * (1024 * 1024 + 1))
        result = salvage_zip(self.source, self.target, max_file_mib=1)
        self.assertEqual(result['recovered_count'], 0)
        self.assertEqual(len(result['skipped']), 1)

if __name__ == '__main__':
    unittest.main()
