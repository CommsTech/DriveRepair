import json
import os
import tempfile
import unittest
from pathlib import Path

from driverepair_desktop.cli import run
from driverepair_desktop.media_refresh import (
    STATE_WRITING,
    ImageReadWriter,
    refresh_media,
    require_destructive_acknowledgements,
    _sha256,
    _atomic_write_bytes,
)


class AckTests(unittest.TestCase):
    def test_missing_flags_fail_closed(self):
        with self.assertRaises(ValueError) as ctx:
            require_destructive_acknowledgements(
                ack_risk=True, ack_destructive=True, ack_no_backup=False,
                ack_data_loss_risk=True, ack_usb_bridge_risk=True, bus="usb",
            )
        self.assertIn("--ack-no-backup", str(ctx.exception))

    def test_live_requires_unvalidated_ack(self):
        with self.assertRaises(ValueError) as ctx:
            require_destructive_acknowledgements(
                ack_risk=True, ack_destructive=True, ack_no_backup=True,
                ack_data_loss_risk=True, ack_usb_bridge_risk=True, bus="usb",
                ack_unvalidated_hardware=False, require_unvalidated=True,
            )
        self.assertIn("--ack-unvalidated-hardware", str(ctx.exception))


class RollingJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "patient.img"
        self.raw = bytes((i * 17) % 256 for i in range(8192))
        self.path.write_bytes(self.raw)
        self.journal = str(Path(self.tmp.name) / "journal")

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_rewrite_preserves_bytes(self):
        media = ImageReadWriter(str(self.path))
        try:
            result = refresh_media(
                media, size=len(self.raw), sector=512, source_token="tok",
                journal=self.journal, chunk=1024, mode="full", verify=True,
                consistency_reads=2,
            )
        finally:
            media.close()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["rewritten_bytes"], len(self.raw))
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertTrue((Path(self.journal) / "meta.json").is_file())
        self.assertFalse((Path(self.journal) / "region.bin").exists())

    def test_failed_reads_never_rewritten(self):
        class Flaky(ImageReadWriter):
            def read_at(self, offset, count):
                if offset == 2048:
                    raise OSError(5, "simulated media read failure")
                return super().read_at(offset, count)

        media = Flaky(str(self.path))
        try:
            result = refresh_media(
                media, size=len(self.raw), sector=512, source_token="tok",
                journal=self.journal, chunk=1024, mode="full", verify=False,
                consistency_reads=2, max_errors=100,
            )
        finally:
            media.close()
        self.assertTrue(any(start == 2048 for start, _ in result["skipped_ranges"]))
        self.assertEqual(self.path.read_bytes()[2048:3072], self.raw[2048:3072])

    def test_inconsistent_reads_are_skipped(self):
        class Flip(ImageReadWriter):
            def __init__(self, path):
                super().__init__(path)
                self.calls = 0

            def read_at(self, offset, count):
                data = bytearray(super().read_at(offset, count))
                if offset == 1024:
                    self.calls += 1
                    if self.calls == 2:
                        data[0] ^= 0xFF
                return bytes(data)

        media = Flip(str(self.path))
        try:
            result = refresh_media(
                media, size=len(self.raw), sector=512, source_token="tok",
                journal=self.journal, chunk=1024, mode="full", verify=False,
                consistency_reads=2,
            )
        finally:
            media.close()
        self.assertTrue(any(start == 1024 for start, _ in result["inconsistent_ranges"]))
        self.assertEqual(self.path.read_bytes()[1024:2048], self.raw[1024:2048])

    def test_resume_restores_writing_transaction_from_journal(self):
        """Fault injection: crash after SAVED→WRITING marker, then resume."""
        media = ImageReadWriter(str(self.path))
        # Manually craft an interrupted WRITING transaction with preserved bytes.
        os.makedirs(self.journal, mode=0o700)
        region = self.raw[0:1024]
        blob = Path(self.journal) / "region.bin"
        _atomic_write_bytes(str(blob), region)
        # Corrupt on-disk region to simulate torn write.
        media.write_at(0, b"\x00" * 1024)
        media.flush()
        meta = {
            "schema": 2,
            "operation": "media_refresh_rolling",
            "mode": "full",
            "size": len(self.raw),
            "sector": 512,
            "chunk": 1024,
            "source_token": "tok",
            "verify": True,
            "consistency_reads": 2,
            "cursor": 0,
            "queue": None,
            "rewritten_bytes": 0,
            "verified_bytes": 0,
            "skipped_ranges": [],
            "inconsistent_ranges": [],
            "failed_read_attempts": 0,
            "failed_write_attempts": 0,
            "transaction": {
                "state": STATE_WRITING,
                "offset": 0,
                "length": 1024,
                "sha256": _sha256(region),
            },
            "status": "in_progress",
            "notes": "test",
        }
        from driverepair_desktop.recovery import _state_save
        _state_save(str(Path(self.journal) / "meta.json"), meta)
        try:
            result = refresh_media(
                media, size=len(self.raw), sector=512, source_token="tok",
                journal=self.journal, chunk=1024, mode="full", verify=True,
                resume=True, consistency_reads=2,
            )
        finally:
            media.close()
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertIn(result["status"], {"completed", "completed_with_skips_or_verify_failures"})
        self.assertIsNone(result["transaction"])

    def test_adaptive_refreshes_only_slow_regions(self):
        class SlowSpot(ImageReadWriter):
            def read_at(self, offset, count):
                if offset == 4096:
                    import time
                    time.sleep(0.02)
                return super().read_at(offset, count)

        media = SlowSpot(str(self.path))
        try:
            result = refresh_media(
                media, size=len(self.raw), sector=512, source_token="tok",
                journal=self.journal, chunk=1024, mode="adaptive", verify=True,
                consistency_reads=2, adaptive_samples=8, slow_multiplier=1.5,
            )
        finally:
            media.close()
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertGreaterEqual(result["rewritten_bytes"], 1024)
        self.assertLess(result["rewritten_bytes"], len(self.raw))

    def test_cli_full_refresh_image(self):
        code = run([
            "refresh-image", "--image", str(self.path), "--journal", self.journal,
            "--mode", "full",
            "--ack-risk", "--ack-destructive", "--ack-no-backup", "--ack-data-loss-risk",
            "--json",
        ])
        self.assertEqual(code, 0)
        self.assertEqual(self.path.read_bytes(), self.raw)
        state = json.loads((Path(self.journal) / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(state["operation"], "media_refresh_rolling")
        self.assertEqual(state["mode"], "full")


if __name__ == "__main__":
    unittest.main()
