"""No hardware access: SMR profiles, 10% sampling, calibration and neighbors."""
import errno
import unittest

from driverepair_desktop.media_profiles import (
    identify_profile, format_quick_preflight, MIB,
)
from driverepair_desktop.guided_repair import tuned_scan, inspect_adjacent_regions
from driverepair_desktop.scanner import scan_offsets, scan_reader
from driverepair_desktop.adaptive_scan import calibrate_initial_read
from driverepair_desktop.devices import _windows_devices_from_get_disk


class SyntheticReader:
    def __init__(self, size, corrupt_at=None):
        self.size = size
        self.calls = []
        self.corrupt_at = corrupt_at
        self.writes = 0

    def read_at(self, off, length):
        self.calls.append((off, length))
        if self.corrupt_at is not None and off <= self.corrupt_at < off + length:
            err = OSError(errno.EINVAL, 'Windows IO')
            err.winerror = 1117
            raise err
        return b'A' * length


class MediaProfileTests(unittest.TestCase):
    def test_seagate_model_confirmed_smr_even_with_usb(self):
        for label in ('ST1000LM048', 'ST1000LM 048-2E7172', 'ATA ST1000LM048'):
            p = identify_profile(model=label, bus='usb', sector=512)
            self.assertEqual(p.kind, 'smr')
            self.assertFalse(p.neighbor_rewrite)
            self.assertEqual(p.quick_fraction, .1)

    def test_smr_model_prefix_is_not_authoritative(self):
        for label in ('ST1000LM0480', 'ST1000LM048EXTRA', 'XXST1000LM048'):
            self.assertEqual(identify_profile(model=label, bus='usb').kind, 'unknown')

    def test_usb_does_not_imply_cmr_or_ssd(self):
        p = identify_profile(model='mystery drive', bus='usb')
        self.assertEqual(p.kind, 'unknown')
        self.assertFalse(p.neighbor_rewrite)

    def test_nvme_and_ssd_do_not_get_adjacent_write_policy(self):
        for p in (identify_profile(bus='nvme'), identify_profile(media_type='ssd')):
            self.assertIn(p.kind, ('ssd', 'nvme'))
            self.assertFalse(p.neighbor_rewrite)

    def test_quick_10_percent_on_one_and_twelve_tb(self):
        for capacity in (10**12, 12*10**12):
            x = tuned_scan(size=capacity, sector=512, mode='quick', bus='usb')
            self.assertEqual(x['requested_coverage_pct'], 10.0)
            self.assertLessEqual(x['samples'], 100000)
            offsets = list(scan_offsets(capacity, x['chunk'], 'triage', x['samples']))
            self.assertEqual(len(offsets), len(set(a for a, _ in offsets)))
            self.assertGreaterEqual(sum(length for _, length in offsets), capacity // 10)
            self.assertLess(sum(length for _, length in offsets), capacity * .12)

    def test_sampling_seed_changes_unvisited_regions_without_losing_coverage(self):
        capacity = 10**12
        plan = tuned_scan(size=capacity, sector=512, mode='quick', bus='usb')
        a = list(scan_offsets(capacity, plan['chunk'], 'triage', plan['samples'], 101))
        b = list(scan_offsets(capacity, plan['chunk'], 'triage', plan['samples'], 202))
        self.assertNotEqual(a, b)
        self.assertEqual(a, list(scan_offsets(capacity, plan['chunk'], 'triage', plan['samples'], 101)))
        self.assertGreaterEqual(sum(length for _, length in a), capacity // 10)
        self.assertGreaterEqual(sum(length for _, length in b), capacity // 10)

    def test_exact_unique_coverage_not_double_counted(self):
        capacity = 64*MIB
        reader = SyntheticReader(capacity)
        x = tuned_scan(size=capacity, sector=512, mode='quick', bus='usb')
        out = scan_reader(reader, size=capacity, sector=512, mode=x['mode'],
                          samples=x['samples'], chunk=x['chunk'], compare_suspects=True)
        self.assertGreaterEqual(out['surface_coverage_pct'], 10.0)
        self.assertLessEqual(out['surface_coverage_pct'], 100.0)
        self.assertEqual(reader.writes, 0)
        self.assertEqual(out['unique_address_bytes'], out['attempted_bytes'])

    def test_quick_preflight_covers_small_large_and_unknown_size(self):
        small = format_quick_preflight(64 * MIB)
        large = format_quick_preflight(10**12)
        unknown = format_quick_preflight(None)
        self.assertIn('10%', small)
        self.assertIn('assumed 120 MiB/s', small)
        self.assertIn('not a duration guarantee', large)
        self.assertIn('capacity unknown', unknown)
        self.assertNotIn('health certificate', unknown)  # only in sized path
        self.assertIn('health certificate', small)

    def test_calibration_only_reads_and_bounds(self):
        reader = SyntheticReader(64*MIB)
        result = calibrate_initial_read(reader, size=64*MIB, sector=512)
        self.assertFalse(result['ended_on_error'])
        self.assertIn(result['chosen_chunk'], {1,2,4,8,16} if False else {MIB,2*MIB,4*MIB,8*MIB,16*MIB})
        self.assertLessEqual(len(reader.calls), 5)
        self.assertEqual(reader.writes, 0)

    def test_calibration_stops_on_media_failure(self):
        reader = SyntheticReader(64*MIB, corrupt_at=2*MIB)
        result = calibrate_initial_read(reader, size=64*MIB, sector=512)
        self.assertTrue(result['ended_on_error'])
        self.assertEqual(result['error_class'], 'io_device_error_unconfirmed_media')
        self.assertLessEqual(len(reader.calls), 3)

    def test_neighborhood_checks_both_sides_without_writes(self):
        reader = SyntheticReader(8*MIB)
        out = inspect_adjacent_regions(reader, size=8*MIB, sector=512,
                                       targets=[(2*MIB,MIB)], window=256*1024)
        self.assertEqual(out['consistent_neighbors'], [(2*MIB-256*1024,256*1024),
                                                        (3*MIB,256*1024)])
        self.assertEqual(reader.writes, 0)
        self.assertFalse(out['original_bytes_proven_correct'])

    def test_neighbor_overlapping_error_quarantined(self):
        reader = SyntheticReader(8*MIB)
        out = inspect_adjacent_regions(reader, size=8*MIB, sector=512,
                                       targets=[(2*MIB,MIB)], window=256*1024,
                                       excluded=[{'offset':3*MIB,'length':512}])
        self.assertEqual(len(out['consistent_neighbors']), 1)
        self.assertNotIn((3*MIB,256*1024), out['consistent_neighbors'])

    def test_targeted_windows_identity_query_rejects_system_drive(self):
        import json
        def fake_run(cmd, timeout=None):
            self.assertIn('Get-Disk -Number 2', cmd[-1])
            self.assertEqual(timeout, 8)
            return json.dumps({'Number':2,'FriendlyName':'Disk', 'SerialNumber':'SERIAL',
                              'Size':4096,'LogicalSectorSize':512,'BusType':'USB',
                              'IsBoot':True,'IsSystem':False,'IsOffline':False}).encode()
        self.assertEqual(_windows_devices_from_get_disk(fake_run, 2), [])


if __name__ == '__main__':
    unittest.main()
