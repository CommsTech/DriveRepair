"""No physical-drive tests: boundary probing and mounted-volume safety."""
import errno
import unittest
from unittest import mock

from driverepair_desktop.guided_repair import inspect_failed_boundaries
from driverepair_desktop.media_refresh import _windows_lock_paths, assert_patient_idle_windows
from driverepair_desktop.cli import parser


class FaultReader:
    def __init__(self, failed, size=8192, disconnected=False):
        self.failed = set(failed)
        self.calls = []
        self.size = size
        self.disconnected = disconnected

    def read_at(self, off, count):
        self.calls.append((off, count))
        if self.disconnected:
            raise OSError(errno.ENODEV, 'removed')
        if any(off <= x < off + count for x in self.failed):
            raise OSError(errno.EIO, 'bad read')
        return bytes([off // 512 % 251]) * count


class NeighborTests(unittest.TestCase):
    def test_both_sides_observed_and_never_written(self):
        reader = FaultReader({2048, 2560})
        result = inspect_failed_boundaries(reader, [{'offset': 2048, 'length': 1024}],
                                           size=8192, sector=512, probe_bytes=512)
        sides = result['regions'][0]['neighbors']
        self.assertEqual(sides['left']['status'], 'boundary_observed')
        self.assertEqual(sides['right']['status'], 'boundary_observed')
        self.assertFalse(result['repair_authorized'])
        self.assertTrue(result['no_writes'])
        self.assertLessEqual(result['read_calls'], 24)

    def test_near_end_never_reads_outside_patient(self):
        reader = FaultReader({0})
        result = inspect_failed_boundaries(reader, [{'offset': 0, 'length': 512}],
                                           size=8192, sector=512, probe_bytes=512)
        self.assertEqual(result['regions'][0]['neighbors']['left']['status'], 'drive_boundary')
        self.assertTrue(all(off >= 0 and off + length <= 8192 for off, length in reader.calls))

    def test_budget_binds_investigation(self):
        reader = FaultReader(range(0,8192,512))
        result = inspect_failed_boundaries(reader, [{'offset': 2048, 'length': 512}],
                                           size=8192, sector=512, probe_bytes=512,
                                           max_probes=2)
        self.assertTrue(result['budget_exhausted'])
        self.assertLessEqual(len(reader.calls), 2)

    def test_disconnected_device_is_not_considered_a_good_boundary(self):
        reader = FaultReader(set(), disconnected=True)
        result = inspect_failed_boundaries(reader, [{'offset': 2048, 'length': 512}],
                                           size=8192, sector=512, probe_bytes=512)
        self.assertEqual(result['regions'][0]['neighbors']['left']['status'], 'device_unavailable')

    def test_invalid_data_is_never_passed_to_reader(self):
        reader = FaultReader(set())
        result = inspect_failed_boundaries(reader,[{'offset':-1,'length':512}],
                                           size=8192,sector=512)
        self.assertEqual(result['regions'], [])
        self.assertEqual(reader.calls, [])

    def test_quick_scan_includes_two_sided_error_boundary_evidence(self):
        from driverepair_desktop.scanner import scan_reader
        reader = FaultReader({4096}, size=32768)
        result = scan_reader(reader, size=32768, sector=512, chunk=4096,
                             mode='triage', samples=8, sample_seed=9,
                             max_errors=100)
        self.assertGreaterEqual(result['read_error_chunks'], 1)
        self.assertTrue(result['error_boundary_investigation']['regions'])
        self.assertFalse(result['error_boundary_investigation']['repair_authorized'])
        self.assertTrue(all(off >= 0 and off + count <= 32768 for off, count in reader.calls))



class WindowsVolumeTests(unittest.TestCase):
    def test_existing_letter_requires_explicit_option(self):
        partitions = [{'Paths': ['E:\\']}]
        with self.assertRaisesRegex(RuntimeError, 'explicitly approve'):
            _windows_lock_paths(partitions, allow_mounted=False)
        self.assertEqual(_windows_lock_paths(partitions, allow_mounted=True), ['\\\\.\\E:'])

    def test_guid_preferred_per_partition(self):
        guid = '\\\\?\\Volume{1234}\\'
        partitions = [{'Paths': ['E:\\', guid]}, {'Paths': ['F:\\']}]
        self.assertEqual(_windows_lock_paths(partitions, allow_mounted=True),
                         [guid[:-1], '\\\\.\\F:'])

    def test_unknown_path_is_never_force_dismounted(self):
        with self.assertRaisesRegex(RuntimeError, 'Unsupported'):
            _windows_lock_paths([{'Paths': ['C:\\MountedFolder']}], allow_mounted=True)

    def test_multiple_or_duplicate_handles_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'Ambiguous'):
            _windows_lock_paths([{'Paths': ['E:\\', 'F:\\']}], allow_mounted=True)
        with self.assertRaisesRegex(RuntimeError, 'Duplicate'):
            _windows_lock_paths([{'Paths': ['E:\\']}, {'Paths': ['E:\\']}], allow_mounted=True)

    def test_option_is_specific_to_write_commands(self):
        parser_instance = parser()
        args = parser_instance.parse_args(['care-external', '--device', 'windows:PhysicalDrive2',
                                  '--auto-lock-volumes'])
        self.assertTrue(args.auto_lock_volumes)
        with self.assertRaises(SystemExit):
            parser_instance.parse_args(['care-image', '--image', 'disk.img', '--auto-lock-volumes'])


if __name__ == '__main__':
    unittest.main()
