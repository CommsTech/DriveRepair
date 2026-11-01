import os
import tempfile
import unittest
from pathlib import Path

from driverepair_desktop.cli import run
from driverepair_desktop.encryption import (
    inspect_boot_sector,
    require_plaintext_filesystem,
    scan_path_for_encryption,
)


def _bitlocker_vbr() -> bytes:
    # Minimal fake VBR with BitLocker OEM name at offset 3.
    sector = bytearray(512)
    sector[0:3] = b"\xeb\x58\x90"
    sector[3:11] = b"-FVE-FS-"
    sector[510:512] = b"\x55\xaa"
    return bytes(sector)


class EncryptionDetectTests(unittest.TestCase):
    def test_inspect_boot_sector_bitlocker(self):
        hit = inspect_boot_sector(_bitlocker_vbr())
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.kind, "bitlocker")
        self.assertEqual(hit.confidence, "high")

    def test_scan_path_finds_bitlocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patient.img"
            path.write_bytes(_bitlocker_vbr() + os.urandom(4096))
            findings = scan_path_for_encryption(str(path))
            self.assertTrue(any(f.kind == "bitlocker" for f in findings))

    def test_require_plaintext_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patient.img"
            path.write_bytes(_bitlocker_vbr() + b"\x00" * 2048)
            with self.assertRaises(ValueError) as ctx:
                require_plaintext_filesystem(str(path), operation="file carving")
            self.assertIn("--ack-encrypted-volume", str(ctx.exception))
            # Explicit ack bypasses hard stop (still returns findings).
            findings = require_plaintext_filesystem(
                str(path), ack_encrypted_volume=True, operation="file carving",
            )
            self.assertTrue(findings)

    def test_plain_ntfs_oem_not_flagged_as_bitlocker(self):
        sector = bytearray(512)
        sector[3:11] = b"NTFS    "
        self.assertIsNone(inspect_boot_sector(bytes(sector)))

    def test_cli_inspect_and_carve_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "enc.img"
            image.write_bytes(_bitlocker_vbr() + b"\x00" * 8192)
            out = Path(tmp) / "carved"
            out.mkdir()
            code = run(["inspect-encryption", "--image", str(image), "--json"])
            self.assertEqual(code, 0)
            code = run([
                "carve-image", "--image", str(image), "--output-dir", str(out), "--json",
            ])
            self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
