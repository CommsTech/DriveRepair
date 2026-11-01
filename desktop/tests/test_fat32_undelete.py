import os
import struct
import tempfile
import unittest
from pathlib import Path

from driverepair_desktop.fat32_undelete import undelete_fat32


def fat32_image(path: Path, *, allocated=False, nested=False):
    data = bytearray(96 * 512)
    data[0:3] = b'\xeb\x58\x90'
    struct.pack_into('<H', data, 11, 512)
    data[13] = 1                         # 1 sector per cluster
    struct.pack_into('<H', data, 14, 32)   # 32 reserved sectors
    data[16] = 1                         # single FAT
    struct.pack_into('<I', data, 32, 96)  # total sectors
    struct.pack_into('<I', data, 36, 1)   # FAT size
    struct.pack_into('<I', data, 44, 2)   # root cluster
    data[510:512] = b'\x55\xaa'
    # FAT occupies sector 32, data region starts sector 33
    for cluster, val in ((0, 0xffffffF8), (1, 0x0FFFFFFF), (2, 0x0FFFFFFF),
                         (3, 0x0FFFFFFF if allocated else 0), (5, 0x0FFFFFFF)):
        struct.pack_into('<I', data, 32 * 512 + cluster * 4, val)
    if nested:
        pos = 33 * 512
        data[pos:pos + 11] = b'SUBFOLDER  '
        data[pos + 11] = 0x10
        struct.pack_into('<H', data, pos + 26, 5)
        pos = (33 + 3) * 512   # cluster 5 directory
    else:
        pos = 33 * 512
    data[pos:pos + 11] = b'\xe5ECOVER TXT'
    data[pos + 11] = 0x20
    struct.pack_into('<H', data, pos + 26, 3)
    payload = b'Deleted file content recovered from FAT32 image'
    struct.pack_into('<I', data, pos + 28, len(payload))
    data[34*512:34*512+len(payload)] = payload
    path.write_bytes(data)
    return payload


class UndeleteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src = self.root / 'fat32.img'
        self.out = self.root / 'restored'

    def test_deleted_contiguous_file_is_extracted_and_explicitly_unverified(self):
        content = fat32_image(self.src)
        result = undelete_fat32(str(self.src), str(self.out))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['files_recovered'], 1)
        self.assertIn('UNVERIFIED', result['files'][0]['confidence'])
        self.assertEqual((self.out / result['files'][0]['filename']).read_bytes(), content)
        self.assertEqual(self.src.stat().st_size, 96 * 512)

    def test_allocated_clusters_not_extracted(self):
        fat32_image(self.src, allocated=True)
        result = undelete_fat32(str(self.src), str(self.out))
        self.assertEqual(result['files_recovered'], 0)
        self.assertEqual(result['skipped']['cluster_reallocated'], 1)

    def test_active_nested_directory_is_searched(self):
        fat32_image(self.src, nested=True)
        result = undelete_fat32(str(self.src), str(self.out))
        self.assertEqual(result['files_recovered'], 1)

    def test_unknown_filesystem_fails_before_creating_output(self):
        self.src.write_bytes(b'0' * 4096)
        with self.assertRaises(ValueError):
            undelete_fat32(str(self.src), str(self.out))
        self.assertFalse(self.out.exists())

    def test_source_symlink_is_rejected(self):
        fat32_image(self.src)
        link = self.root / 'alias.img'
        link.symlink_to(self.src)
        with self.assertRaises(ValueError):
            undelete_fat32(str(link), str(self.out))
        self.assertFalse(self.out.exists())

    def test_recovery_journal_incomplete_blocks_undelete(self):
        import json
        fat32_image(self.src)
        Path(str(self.src) + '.rescue.json').write_text(json.dumps({'status': 'completed_with_missing_data'}))
        with self.assertRaises(RuntimeError):
            undelete_fat32(str(self.src), str(self.out))
        self.assertFalse(self.out.exists())

if __name__ == '__main__':
    unittest.main()
