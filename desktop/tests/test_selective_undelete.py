"""Safety tests: list first, restore only explicitly requested candidates."""
import hashlib
import tempfile
import unittest
from pathlib import Path
import struct

from driverepair_desktop.fat32_undelete import list_deleted_fat32, undelete_fat32
from test_fat32_undelete import fat32_image


class SelectiveRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'source.img'
        self.out = Path(self.tmp.name) / 'selected'
        self.first = fat32_image(self.path)
        data = bytearray(self.path.read_bytes())
        start = 33 * 512 + 32
        data[start:start+11] = b'\xe5ECOND  BIN'
        data[start+11] = 0x20
        struct.pack_into('<H', data, start+26, 4)
        self.second = b'Second test candidate'
        struct.pack_into('<I', data, start+28, len(self.second))
        data[35*512:35*512 + len(self.second)] = self.second
        self.path.write_bytes(data)

    def test_catalog_does_not_write_or_create_output(self):
        before = hashlib.sha256(self.path.read_bytes()).digest()
        one = list_deleted_fat32(str(self.path))
        two = list_deleted_fat32(str(self.path))
        self.assertEqual(one['candidates_found'], 2)
        self.assertEqual([x['id'] for x in one['candidates']],
                         [x['id'] for x in two['candidates']])
        self.assertTrue(all(x['eligible'] for x in one['candidates']))
        self.assertEqual(before, hashlib.sha256(self.path.read_bytes()).digest())
        self.assertFalse(self.out.exists())

    def test_restore_only_selected_second_candidate(self):
        before = self.path.read_bytes()
        candidates = list_deleted_fat32(str(self.path))['candidates']
        result = undelete_fat32(str(self.path), str(self.out),
                                selected_ids=[candidates[1]['id']])
        self.assertEqual(result['files_recovered'], 1)
        self.assertEqual((self.out / result['files'][0]['filename']).read_bytes(), self.second)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertNotIn('ECOVER', result['files'][0]['filename'])

    def test_unknown_selection_refused_before_output_creation(self):
        with self.assertRaises(ValueError):
            undelete_fat32(str(self.path), str(self.out), selected_ids=['0'*20])
        self.assertFalse(self.out.exists())

    def test_reallocated_candidate_is_listed_but_not_extractable(self):
        data = bytearray(self.path.read_bytes())
        struct.pack_into('<I', data, 32*512 + 4*4, 0x0fffffff)
        self.path.write_bytes(data)
        candidates = list_deleted_fat32(str(self.path))['candidates']
        self.assertFalse(candidates[1]['eligible'])
        with self.assertRaises(ValueError):
            undelete_fat32(str(self.path), str(self.out), selected_ids=[candidates[1]['id']])
        self.assertFalse(self.out.exists())

    def test_duplicate_selection_is_refused(self):
        candidate = list_deleted_fat32(str(self.path))['candidates'][0]['id']
        with self.assertRaises(ValueError):
            undelete_fat32(str(self.path), str(self.out), selected_ids=[candidate, candidate])

if __name__ == '__main__':
    unittest.main()
