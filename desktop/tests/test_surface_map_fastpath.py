"""Sequential fast path may improve performance without changing truthful counts."""
import unittest
from driverepair_desktop.surface_map import SurfaceCoverage


class SequentialCoverageTests(unittest.TestCase):
    def test_adjacent_and_duplicate_reads_count_once(self):
        cov=SurfaceCoverage(4096,cells=4)
        for offset in range(0,4096,128):
            cov.observe(offset,128)
            cov.observe(offset,128)  # retry is not new coverage
        self.assertEqual(cov.checked_bytes,4096)
        self.assertEqual(cov.coverage_pct,100.0)
        self.assertTrue(all(len(c.intervals)==1 for c in cov.cells))

    def test_sparse_out_of_order_union_and_error_are_not_counted(self):
        cov=SurfaceCoverage(1000,cells=1)
        cov.observe(700,100)
        cov.observe(100,100)
        cov.observe(150,650)
        cov.observe(0,100,failed=True)
        self.assertEqual(cov.checked_bytes,700)
        self.assertEqual(cov.cells[0].read_errors,1)
        cov.observe(0,100)
        cov.observe(800,200)
        self.assertEqual(cov.checked_bytes,1000)

    def test_slow_reads_are_observed_without_extra_coverage(self):
        cov=SurfaceCoverage(1024,cells=1)
        cov.observe(0,512,slow=True)
        cov.observe(0,512,slow=True)
        self.assertEqual(cov.checked_bytes,512)
        self.assertEqual(cov.cells[0].slow_reads,2)


if __name__=='__main__':
    unittest.main()
