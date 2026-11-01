"""Tests for filesystem detection, NTFS undelete, and unified recover-image."""
from __future__ import annotations

import json
import os
import struct
import tempfile
import unittest

from driverepair_desktop.filesystems.detect import detect_filesystems
from driverepair_desktop.filesystems.ntfs import undelete_ntfs
from driverepair_desktop.filesystems.recover import recover_image
from driverepair_desktop import cli


def _ntfs_boot(mft_lcn: int = 2, bps: int = 512, spc: int = 1) -> bytes:
    boot = bytearray(512)
    boot[0:3] = b"\xeb\x52\x90"
    boot[3:11] = b"NTFS    "
    struct.pack_into("<H", boot, 0x0B, bps)
    boot[0x0D] = spc
    struct.pack_into("<q", boot, 0x30, mft_lcn)
    boot[0x40] = 0xF6  # 2^(-10) => 1024-byte records (signed -10)
    # Actually -10 as signed byte: struct pack b
    struct.pack_into("<b", boot, 0x40, -10)
    boot[510:512] = b"\x55\xaa"
    return bytes(boot)


def _mft_record_deleted_resident(name: str, payload: bytes, record_size: int = 1024) -> bytes:
    rec = bytearray(record_size)
    rec[0:4] = b"FILE"
    struct.pack_into("<H", rec, 0x04, 0x30)  # usa offset (unused in synthetic)
    struct.pack_into("<H", rec, 0x06, 0)     # usa count 0 → fixup allows zero path carefully
    # Use usa_count=0 disabled — our fixup requires count>=2. Build a valid USA.
    struct.pack_into("<H", rec, 0x04, 0x28)
    struct.pack_into("<H", rec, 0x06, 3)  # header + 2 sectors for 1024
    # Place USA at 0x28: seq + two replacements matching ends before fixup
    rec[0x28:0x2A] = b"\x01\x00"
    # First attribute at 0x38
    struct.pack_into("<H", rec, 0x14, 0x38)
    struct.pack_into("<H", rec, 0x16, 0x0000)  # deleted file
    struct.pack_into("<I", rec, 0x18, record_size)
    struct.pack_into("<I", rec, 0x1C, record_size)

    # $FILE_NAME resident attribute
    name_utf16 = name.encode("utf-16le")
    fn_content = bytearray(0x42 + len(name_utf16))
    fn_content[0x40] = len(name)
    fn_content[0x42:0x42 + len(name_utf16)] = name_utf16
    fn_attr = bytearray(24 + len(fn_content))
    struct.pack_into("<I", fn_attr, 0, 0x30)
    struct.pack_into("<I", fn_attr, 4, len(fn_attr))
    fn_attr[8] = 0  # resident
    struct.pack_into("<I", fn_attr, 16, len(fn_content))
    struct.pack_into("<H", fn_attr, 20, 24)
    fn_attr[24:] = fn_content

    # $DATA resident
    data_attr = bytearray(24 + len(payload))
    struct.pack_into("<I", data_attr, 0, 0x80)
    struct.pack_into("<I", data_attr, 4, len(data_attr))
    data_attr[8] = 0
    struct.pack_into("<I", data_attr, 16, len(payload))
    struct.pack_into("<H", data_attr, 20, 24)
    data_attr[24:] = payload

    pos = 0x38
    rec[pos:pos + len(fn_attr)] = fn_attr
    pos += len(fn_attr)
    rec[pos:pos + len(data_attr)] = data_attr
    pos += len(data_attr)
    struct.pack_into("<I", rec, pos, 0xFFFFFFFF)

    # Set sector end markers to USA sequence before fixup application expects match
    rec[510:512] = b"\x01\x00"
    rec[1022:1024] = b"\x01\x00"
    # USA replacements store original (zeros)
    rec[0x2A:0x2E] = b"\x00\x00\x00\x00"
    return bytes(rec)


class FilesystemRecoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_detect_ntfs_boot(self):
        path = os.path.join(self.tmp.name, "ntfs.img")
        with open(path, "wb") as f:
            f.write(_ntfs_boot())
            f.write(b"\x00" * (512 * 8))
        found = detect_filesystems(path)
        kinds = [d.kind for d in found]
        self.assertIn("ntfs", kinds)

    def test_ntfs_undelete_resident_deleted(self):
        path = os.path.join(self.tmp.name, "ntfs_del.img")
        boot = _ntfs_boot(mft_lcn=1, spc=1)
        record = _mft_record_deleted_resident("notes.txt", b"hello-ntfs-undelete")
        # Layout: boot at 0, MFT at cluster 1 => offset 512
        with open(path, "wb") as f:
            f.write(boot)
            f.write(record)
            f.write(b"\x00" * 2048)
        out = os.path.join(self.tmp.name, "out_ntfs")
        result = undelete_ntfs(path, out, max_files=10)
        self.assertEqual(result["status"], "completed")
        self.assertGreaterEqual(result["files_recovered"], 1)
        recovered = result["files"][0]
        with open(os.path.join(out, recovered["filename"]), "rb") as fh:
            data = fh.read()
        self.assertEqual(data, b"hello-ntfs-undelete")
        self.assertIn("notes.txt", recovered.get("original_name", ""))

    def test_recover_image_raw_mode_carves_pdf(self):
        path = os.path.join(self.tmp.name, "raw.img")
        pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
        with open(path, "wb") as f:
            f.write(b"\x00" * 64 + pdf + b"\x00" * 64)
        out = os.path.join(self.tmp.name, "out_raw")
        result = recover_image(path, out, mode="raw", max_files=10, raw_formats=("pdf",))
        self.assertEqual(result["status"], "completed")
        self.assertGreaterEqual(result["raw_pass"]["files_carved"], 1)

    def test_cli_detect_filesystems(self):
        path = os.path.join(self.tmp.name, "cli_ntfs.img")
        with open(path, "wb") as f:
            f.write(_ntfs_boot())
            f.write(b"\x00" * 4096)
        code = cli.run(["detect-filesystems", "--image", path, "--json"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
