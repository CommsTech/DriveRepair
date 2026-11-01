import errno
import unittest
from driverepair_desktop.scanner import scan_offsets, scan_reader


class TestReader:
    def __init__(self, count: int, bad: set[int] | None = None):
        self.size = count
        self.bad = bad or set()
        self.reads = []

    def read_at(self, offset, count):
        index = offset // 512
        self.reads.append(index)
        if index in self.bad:
            raise OSError(errno.EIO, 'simulated sector unreadable')
        return b'A' * count

    def close(self):
        pass


class TriageTests(unittest.TestCase):
    def test_offsets_deterministic_and_stratified(self):
        first = list(scan_offsets(512*1000, 512, 'triage', 31))
        self.assertEqual(first, list(scan_offsets(512*1000, 512, 'triage', 31)))
        self.assertEqual(first[0][0], 0)
        self.assertEqual(first[-1][0], 512*999)
        self.assertEqual(len(first), 31)
        self.assertEqual(len(set(first)), len(first))

    def test_responds_to_fault_with_neighbor_check_bounded(self):
        candidates = list(scan_offsets(512*1000, 512, 'triage', 50))
        problem = candidates[24][0] // 512
        reader = TestReader(1000, {problem})
        result = scan_reader(reader, size=512*1000, sector=512, chunk=512,
                             mode='triage', samples=50)
        self.assertEqual(result['status'], 'completed_with_read_errors')
        self.assertGreaterEqual(result['follow_up_chunks'], 1)
        self.assertLessEqual(result['attempted_chunks'], 100)
        self.assertIn(problem - 1, reader.reads)
        self.assertIn(problem + 1, reader.reads)
        self.assertLess(result['surface_coverage_pct'], 100)

    def test_clean_triage_is_not_a_full_scan(self):
        reader = TestReader(1000)
        report = scan_reader(reader, size=512*1000, sector=512, chunk=512,
                             mode='triage', samples=37)
        self.assertEqual(report['status'], 'completed')
        self.assertEqual(report['attempted_chunks'], 37)
        self.assertIn('SPOT-CHECK', report['notes'])
        self.assertLess(report['surface_coverage_pct'], 4)

if __name__ == '__main__':
    unittest.main()
