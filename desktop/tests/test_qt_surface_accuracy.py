"""Tests for truthful whole-drive coverage, distributed sampling and ETA."""
import unittest

from driverepair_desktop.surface_map import SurfaceCoverage
from driverepair_desktop.qtgui import format_eta, progress_percent
from driverepair_desktop.guided_repair import tuned_scan
from driverepair_desktop.scanner import scan_offsets


class SurfaceMapTests(unittest.TestCase):
    def test_sparse_sample_marks_only_actual_bytes(self):
        coverage = SurfaceCoverage(1024 * 1024, cells=4)
        coverage.observe(0, 64 * 1024)
        self.assertEqual(coverage.coverage_pct, 6.25)
        self.assertEqual(coverage.cells[0].fraction, 0.25)
        self.assertEqual(coverage.cells[1].fraction, 0)
        coverage.observe(0, 64 * 1024)
        self.assertEqual(coverage.coverage_pct, 6.25)

    def test_errors_are_not_treated_as_data_recovered(self):
        coverage = SurfaceCoverage(1024, cells=4)
        coverage.observe(0, 256, failed=True)
        self.assertEqual(coverage.coverage_pct, 0)
        self.assertEqual(coverage.cells[0].read_errors, 1)
        coverage.observe(0, 256, slow=True)
        self.assertEqual(coverage.coverage_pct, 25)
        self.assertEqual(coverage.cells[0].slow_reads, 1)
        self.assertEqual(coverage.cells[0].read_errors, 1)

    def test_cross_cell_overlap_and_repeat_never_exaggerates_coverage(self):
        coverage = SurfaceCoverage(1000, cells=10)
        coverage.observe(95, 30)
        coverage.observe(110, 30)
        self.assertEqual(coverage.checked_bytes, 45)
        coverage.observe(100, 20)
        self.assertEqual(coverage.checked_bytes, 45)
        self.assertAlmostEqual(coverage.coverage_pct, 4.5)

    def test_large_drive_fixed_cell_bounds(self):
        coverage = SurfaceCoverage(10**12, cells=384)
        self.assertEqual(coverage.cells[0].start, 0)
        self.assertEqual(coverage.cells[-1].end, 10**12)
        coverage.observe(10**12 - 512, 512)
        self.assertEqual(coverage.checked_bytes, 512)

    def test_quick_is_distributed_10_percent_not_a_prefix(self):
        size=10**12
        plan=tuned_scan(size=size,sector=512,mode='quick',bus='usb',model='ST1000LM048')
        addresses=[off for off, _ in scan_offsets(size,plan['chunk'],'triage',plan['samples'],sample_seed=4)]
        self.assertGreaterEqual(len(set(addresses))*plan['chunk'], size//10)
        self.assertTrue(any(off > size*.9 for off in addresses))
        self.assertTrue(any(off > size*.5 for off in addresses))
        # Bounded seek-order randomization rather than re-reading the first tenth.
        self.assertTrue(any(a > b for a,b in zip(addresses[1:-2], addresses[2:-1])))
        self.assertEqual(addresses[0], 0)

    def test_operation_progress_is_percent_not_fraction(self):
        self.assertEqual(progress_percent({'probe_index':8,'probe_total':8,'scan_mode':'triage','size':10**12}),100.0)
        self.assertEqual(progress_percent({'refresh_index':2,'refresh_total':4,'offset':10**12-512,'size':10**12}),50.0)
        self.assertEqual(progress_percent({'scan_position_bytes':500,'size':1000}),50.0)
        self.assertEqual(progress_percent({},1000),0.0)

    def test_eta_formatting(self):
        self.assertEqual(format_eta(0), '0m 00s')
        self.assertEqual(format_eta(90), '1m 30s')
        self.assertEqual(format_eta(3720), '1h 02m')
        self.assertEqual(format_eta(None), 'Calculating…')


if __name__ == '__main__':
    unittest.main()
