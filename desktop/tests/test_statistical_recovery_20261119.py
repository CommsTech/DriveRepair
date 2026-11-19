"""Fail-closed statistical multi-sample recovery and maintenance levels."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from driverepair_desktop.media_refresh import ImageReadWriter, refresh_media
from driverepair_desktop.statistical_recovery import (
    read_with_statistical_confidence,
    resolve_maintenance_level,
    level_as_refresh_kwargs,
)


class MaintenanceLevelTests(unittest.TestCase):
    def test_aliases_and_ladder(self):
        self.assertEqual(resolve_maintenance_level("quick").level, 1)
        self.assertEqual(resolve_maintenance_level(4).name, "deep")
        deep = resolve_maintenance_level("deep")
        self.assertTrue(deep.allow_sector_majority)
        self.assertGreaterEqual(deep.min_agreement, 0.75)
        kwargs = level_as_refresh_kwargs(deep)
        self.assertEqual(kwargs["statistical_samples"], 8)
        with self.assertRaises(ValueError):
            resolve_maintenance_level("spinrite")


class StatisticalSamplerTests(unittest.TestCase):
    def test_unanimous_agreement(self):
        payload = b"A" * 512
        calls = {"n": 0}

        def read_at(_offset, length):
            calls["n"] += 1
            self.assertEqual(length, 512)
            return payload

        result = read_with_statistical_confidence(
            read_at, 0, 512, samples=3, settle_ms=0, sector=512,
        )
        self.assertEqual(result.method, "unanimous")
        self.assertEqual(result.data, payload)
        self.assertEqual(calls["n"], 3)

    def test_weak_majority_fail_closed(self):
        # 3 samples disagree with no clear 75% winner → refuse
        variants = [b"A" * 512, b"B" * 512, b"C" * 512]
        idx = {"i": 0}

        def read_at(_offset, length):
            blob = variants[idx["i"] % 3]
            idx["i"] += 1
            return blob

        with self.assertRaises(RuntimeError) as ctx:
            read_with_statistical_confidence(
                read_at, 0, 512, samples=3, settle_ms=0,
                min_agreement=0.75, allow_sector_majority=True, sector=512,
            )
        self.assertEqual(str(ctx.exception), "inconsistent_reads")

    def test_sector_majority_at_high_confidence(self):
        # 8 samples: 6 agree on sector 0, 6 agree on sector 1 → 75%
        good0 = b"\x11" * 512
        good1 = b"\x22" * 512
        bad0 = b"\x00" * 512
        bad1 = b"\xff" * 512
        sequence = [
            good0 + good1,
            good0 + good1,
            good0 + good1,
            good0 + good1,
            good0 + good1,
            good0 + good1,
            bad0 + good1,   # sector0 minority
            good0 + bad1,   # sector1 minority
        ]
        idx = {"i": 0}

        def read_at(_offset, length):
            blob = sequence[idx["i"]]
            idx["i"] += 1
            self.assertEqual(length, 1024)
            return blob

        result = read_with_statistical_confidence(
            read_at, 0, 1024, samples=8, settle_ms=0,
            min_agreement=0.75, allow_sector_majority=True, sector=512,
        )
        self.assertEqual(result.method, "sector_majority")
        self.assertEqual(result.data, good0 + good1)
        self.assertGreaterEqual(result.agreement_ratio, 0.75)


class RefreshIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "patient.img"
        self.raw = bytes((i * 13) % 256 for i in range(4096))
        self.path.write_bytes(self.raw)
        self.journal = str(Path(self.tmp.name) / "journal")

    def tearDown(self):
        self.tmp.cleanup()

    def test_refresh_with_normal_level_preserves_bytes(self):
        media = ImageReadWriter(str(self.path))
        try:
            result = refresh_media(
                media, size=len(self.raw), sector=512, source_token="tok",
                journal=self.journal, chunk=1024, mode="full", verify=True,
                consistency_reads=2, statistical_samples=3, settle_ms=1,
                min_agreement=1.0, allow_sector_majority=False,
                maintenance_level=2, maintenance_level_name="normal",
                journal_backend="disk",
            )
        finally:
            media.close()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["maintenance_level_name"], "normal")
        self.assertGreaterEqual(result["unanimous_recoveries"], 1)
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_inconsistent_still_skipped_under_statistical(self):
        class Flip(ImageReadWriter):
            def __init__(self, path):
                super().__init__(path)
                self.n = 0

            def read_at(self, offset, count):
                data = bytearray(super().read_at(offset, count))
                if offset == 1024:
                    self.n += 1
                    data[0] = (data[0] + self.n) % 256
                return bytes(data)

        media = Flip(str(self.path))
        try:
            result = refresh_media(
                media, size=len(self.raw), sector=512, source_token="tok",
                journal=self.journal, chunk=1024, mode="full", verify=False,
                consistency_reads=2, statistical_samples=5, settle_ms=0,
                min_agreement=1.0, allow_sector_majority=False,
                max_errors=100, journal_backend="disk", auto_escalate=False,
            )
        finally:
            media.close()
        self.assertTrue(any(start == 1024 for start, _ in result["inconsistent_ranges"]))
        self.assertEqual(self.path.read_bytes()[1024:2048], self.raw[1024:2048])


if __name__ == "__main__":
    unittest.main()
