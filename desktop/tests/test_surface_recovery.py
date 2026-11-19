import errno
import unittest

from driverepair_desktop.scanner import scan_reader
from driverepair_desktop.surface_recovery import (
    ZoneLatencyBaselines,
    consensus_read,
    sector_drilldown,
)


class SyntheticReader:
    """Deterministic synthetic image with optional per-call corruption."""

    def __init__(self, data, corrupt_on=None, fail_on=None):
        self.data = data
        self.corrupt_on = corrupt_on or set()
        self.fail_on = fail_on or set()
        self.calls = []

    def read_at(self, offset, count):
        index = len(self.calls)
        self.calls.append((offset, count))
        if index in self.fail_on:
            raise OSError(errno.EIO, "injected read failure")
        block = bytearray(self.data[offset:offset + count])
        if index in self.corrupt_on:
            for position in range(0, len(block), 7):
                block[position] ^= 0xFF
        return bytes(block)

    def close(self):
        pass


class ConsensusReadTests(unittest.TestCase):
    def setUp(self):
        self.image = bytes((index * 3) & 0xFF for index in range(64 * 1024))

    def test_majority_wins_over_one_corrupted_attempt(self):
        reader = SyntheticReader(self.image, corrupt_on={1})
        outcome = consensus_read(reader, 4096, 512, sector=512, attempts=3)
        self.assertEqual(outcome["status"], "consensus")
        self.assertEqual(outcome["data"], self.image[4096:4608])
        self.assertGreaterEqual(outcome["agreeing_bytes_pct"], 60.0)
        self.assertLess(outcome["agreeing_bytes_pct"], 100.0)
        self.assertEqual(outcome["distinct_blocks"], 2)

    def test_three_different_answers_is_not_consensus(self):
        class Divergent:
            def __init__(self):
                self.calls = 0

            def read_at(self, offset, count):
                self.calls += 1
                return bytes([(self.calls * 37) & 0xFF]) * count

            def close(self):
                pass

        outcome = consensus_read(Divergent(), 0, 512, sector=512, attempts=3)
        self.assertEqual(outcome["status"], "no_consensus")
        self.assertIsNone(outcome["data"])
        self.assertEqual(outcome["distinct_blocks"], 3)

    def test_single_failed_attempt_still_reaches_consensus(self):
        reader = SyntheticReader(self.image, fail_on={0})
        outcome = consensus_read(reader, 8192, 1024, sector=512, attempts=3)
        self.assertEqual(outcome["status"], "consensus")
        self.assertEqual(outcome["successful_reads"], 2)
        self.assertEqual(outcome["data"], self.image[8192:9216])

    def test_all_attempts_failing_reports_all_failed(self):
        reader = SyntheticReader(self.image, fail_on={0, 1, 2})
        outcome = consensus_read(reader, 0, 512, sector=512, attempts=3)
        self.assertEqual(outcome["status"], "all_failed")
        self.assertEqual(outcome["successful_reads"], 0)
        self.assertIsNone(outcome["data"])

    def test_read_starts_are_varied_and_read_only(self):
        reader = SyntheticReader(self.image)
        consensus_read(reader, 65536, 1024, sector=512, attempts=3,
                       shifts=(-1, 0, 1))
        starts = {offset for offset, _ in reader.calls}
        self.assertEqual(len(starts), 3)
        self.assertTrue(all(count > 0 for _, count in reader.calls))
        self.assertEqual(len(reader.calls), 3)
        self.assertFalse(hasattr(reader, "write_at"))


class ZoneBaselineTests(unittest.TestCase):
    def test_inner_zone_is_not_penalised_for_being_slower(self):
        zones = ZoneLatencyBaselines(zone_bytes=1 << 20, min_samples=4)
        for _ in range(8):
            zones.observe(0, 10.0)
        for _ in range(8):
            zones.observe(5 << 20, 60.0)
        self.assertEqual(zones.classify(0, 10.0)["state"], "normal")
        self.assertEqual(zones.classify(5 << 20, 60.0)["state"], "normal")
        self.assertEqual(zones.classify(5 << 20, 900.0)["state"], "marginal")
        self.assertEqual(zones.classify(0, 900.0)["state"], "marginal")

    def test_sparse_zone_falls_back_to_global_baseline(self):
        zones = ZoneLatencyBaselines(zone_bytes=1 << 20, min_samples=8)
        for _ in range(10):
            zones.observe(0, 20.0)
        zones.observe(9 << 20, 20.0)
        info = zones.classify(9 << 20, 20.0)
        self.assertEqual(info["zone"], 9)
        self.assertEqual(info["state"], "normal")
        self.assertIsNotNone(info["threshold_ms"])

    def test_unknown_before_any_observation(self):
        self.assertEqual(ZoneLatencyBaselines().classify(0, 5.0)["state"], "unknown")


class SectorDrilldownTests(unittest.TestCase):
    def test_locates_failing_sectors_inside_chunk(self):
        image = bytes(4096)

        class FailingOffsets:
            def __init__(self):
                self.calls = []

            def read_at(self, offset, count):
                self.calls.append((offset, count))
                if (offset // 512) % 4 == 3:
                    raise OSError(errno.EIO, "bad sector")
                return image[offset:offset + count]

            def close(self):
                pass

        reader = FailingOffsets()
        outcome = sector_drilldown(reader, 0, 4096, sector=512, max_sectors=8)
        self.assertEqual(outcome["sectors_probed"], 8)
        self.assertEqual(outcome["failed_sector_count"], 2)
        self.assertEqual([item["offset"] for item in outcome["failed_sectors"]],
                         [1536, 3584])
        self.assertTrue(all(count == 512 for _, count in reader.calls))

    def test_probe_count_is_bounded(self):
        image = bytes(64 * 1024)

        class Reader:
            def read_at(self, offset, count):
                return image[offset:offset + count]

            def close(self):
                pass

        outcome = sector_drilldown(Reader(), 0, 64 * 1024, sector=512,
                                   max_sectors=16)
        self.assertEqual(outcome["sectors_in_range"], 128)
        self.assertLessEqual(outcome["sectors_probed"], 16)
        self.assertEqual(outcome["failed_sector_count"], 0)


class ScannerIntegrationTests(unittest.TestCase):
    def test_scan_records_consensus_and_sector_evidence(self):
        image = bytes(4096)

        class Flaky:
            def __init__(self):
                self.calls = []
                self.failures = 0

            def read_at(self, offset, count):
                self.calls.append((offset, count))
                if offset == 0 and self.failures < 2:
                    self.failures += 1
                    raise OSError(errno.EIO, "synthetic read error")
                return image[offset:offset + count]

            def close(self):
                pass

        reader = Flaky()
        result = scan_reader(reader, size=4096, sector=512, mode="triage",
                             samples=4, chunk=1024, compare_suspects=True,
                             max_errors=10)
        self.assertIn("consensus_candidates", result)
        self.assertIn("sector_drilldown", result)
        self.assertTrue(result["sector_drilldown"])
        self.assertTrue(all(count > 0 for _, count in reader.calls))


if __name__ == "__main__":
    unittest.main()
