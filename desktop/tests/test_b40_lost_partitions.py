"""Read-only lost-partition discovery against synthetic images."""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from driverepair_desktop.lost_partitions import scan_lost_partitions


def _mbr_with_partition(start_lba: int, sectors: int, part_type: int = 0x07) -> bytes:
    sector = bytearray(512)
    entry = bytearray(16)
    entry[4] = part_type
    struct.pack_into('<I', entry, 8, start_lba)
    struct.pack_into('<I', entry, 12, sectors)
    sector[446:462] = entry
    sector[510:512] = b'\x55\xaa'
    return bytes(sector)


def _ntfs_boot() -> bytes:
    sector = bytearray(512)
    sector[3:11] = b'NTFS    '
    sector[510:512] = b'\x55\xaa'
    return bytes(sector)


class LostPartitionScanTests(unittest.TestCase):
    def test_mbr_and_signature_candidates(self):
        size = 8 * 1024 * 1024
        start = 2048
        sector = 512
        blob = bytearray(size)
        blob[0:512] = _mbr_with_partition(start, 1024)
        off = start * sector
        blob[off:off + 512] = _ntfs_boot()
        # Orphan signature later in the image (not in MBR)
        orphan = 4 * 1024 * 1024
        blob[orphan:orphan + 512] = _ntfs_boot()

        def read_at(offset, count):
            return bytes(blob[offset:offset + count])

        report = scan_lost_partitions(read_at, size_bytes=size, sector_size=sector)
        self.assertEqual(report['patient_writes'], 0)
        self.assertTrue(report['mbr_present'])
        offsets = {c['offset_bytes'] for c in report['candidates']}
        self.assertIn(off, offsets)
        self.assertIn(orphan, offsets)
        table = [c for c in report['candidates'] if c['confidence'] == 'table']
        self.assertEqual(table[0]['filesystem_hint'], 'ntfs')
        sig = [c for c in report['candidates'] if c['source'] == 'boot_signature_probe']
        self.assertTrue(sig)

    def test_image_cli_path_roundtrip(self):
        from driverepair_desktop.cli import main
        size = 2 * 1024 * 1024
        start = 2048
        blob = bytearray(size)
        blob[0:512] = _mbr_with_partition(start, 512)
        off = start * 512
        blob[off:off + 512] = _ntfs_boot()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'disk.img'
            path.write_bytes(blob)
            # Invoke through module entry by calling scan directly (CLI uses ImageReader)
            from driverepair_desktop.scanner import ImageReader
            reader = ImageReader(str(path))
            try:
                report = scan_lost_partitions(
                    reader.read_at, size_bytes=path.stat().st_size, sector_size=512)
            finally:
                reader.close()
            self.assertGreaterEqual(report['table_backed'], 1)
            self.assertIn('does not rewrite', report['message'])


if __name__ == '__main__':
    unittest.main()
