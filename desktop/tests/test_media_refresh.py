import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from driverepair_desktop.cli import run
from driverepair_desktop.media_refresh import (
    ImageReadWriter,
    refresh_media,
    require_destructive_acknowledgements,
)


class AckTests(unittest.TestCase):
    def test_missing_flags_fail_closed(self):
        with self.assertRaises(ValueError) as ctx:
            require_destructive_acknowledgements(
                ack_risk=True, ack_destructive=True, ack_no_backup=False,
                ack_data_loss_risk=True, ack_usb_bridge_risk=True, bus="usb",
            )
        self.assertIn("--ack-no-backup", str(ctx.exception))

    def test_usb_requires_bridge_ack(self):
        with self.assertRaises(ValueError) as ctx:
            require_destructive_acknowledgements(
                ack_risk=True, ack_destructive=True, ack_no_backup=True,
                ack_data_loss_risk=True, ack_usb_bridge_risk=False, bus="usb",
            )
        self.assertIn("--ack-usb-bridge-risk", str(ctx.exception))


class RefreshImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "patient.img"
        self.raw = bytes((i * 17) % 256 for i in range(8192))
        self.path.write_bytes(self.raw)
        self.journal = str(Path(self.tmp.name) / "refresh.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_rewrite_preserves_bytes_when_reads_succeed(self):
        media = ImageReadWriter(str(self.path))
        try:
            result = refresh_media(
                media, size=len(self.raw), sector=512, source_token="tok",
                journal=self.journal, chunk=1024, verify=True,
            )
        finally:
            media.close()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["rewritten_bytes"], len(self.raw))
        self.assertEqual(result["verified_bytes"], len(self.raw))
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_failed_reads_are_not_overwritten_with_zeros(self):
        class Flaky(ImageReadWriter):
            def read_at(self, offset, count):
                if offset == 2048:
                    raise OSError(5, "simulated read failure")
                return super().read_at(offset, count)

        media = Flaky(str(self.path))
        try:
            result = refresh_media(
                media, size=len(self.raw), sector=512, source_token="tok",
                journal=self.journal, chunk=1024, verify=False, max_errors=100,
            )
        finally:
            media.close()
        self.assertIn(result["status"], {
            "completed_with_skips_or_verify_failures", "completed",
        })
        self.assertTrue(any(start == 2048 for start, _ in result["skipped_ranges"]))
        # Pre-existing bytes at the skipped offset must remain untouched.
        self.assertEqual(self.path.read_bytes()[2048:3072], self.raw[2048:3072])

    def test_cli_requires_acks(self):
        code = run([
            "refresh-image", "--image", str(self.path), "--journal", self.journal,
        ])
        self.assertEqual(code, 1)

    def test_cli_refresh_image_ok(self):
        code = run([
            "refresh-image", "--image", str(self.path), "--journal", self.journal,
            "--ack-risk", "--ack-destructive", "--ack-no-backup", "--ack-data-loss-risk",
            "--json",
        ])
        self.assertEqual(code, 0)
        self.assertEqual(self.path.read_bytes(), self.raw)
        state = json.loads(Path(self.journal).read_text(encoding="utf-8"))
        self.assertEqual(state["operation"], "media_refresh")
        self.assertEqual(state["rewritten_bytes"], len(self.raw))


if __name__ == "__main__":
    unittest.main()
