import errno
import unittest
from driverepair_desktop.benchmark import read_benchmark

class FakeClock:
    def __init__(self):
        self.value = 0.0
    def __call__(self):
        self.value += 0.005
        return self.value

class Device:
    def __init__(self, fail=False):
        self.fail = fail
    def read_at(self, offset, count):
        if self.fail and offset >= 512:
            raise OSError(errno.EIO, 'Injected')
        return b'a' * count
    def close(self):
        pass

class BenchmarkTests(unittest.TestCase):
    def test_complete_sample(self):
        r = read_benchmark(Device(), size=4096, sector=512,
                           samples=8, chunk=512, timer=FakeClock())
        self.assertEqual(r['status'], 'completed')
        self.assertEqual(r['readable_bytes'], 4096)
        self.assertEqual(sum(z['samples'] for z in r['zones']), 8)
        self.assertIsNotNone(r['read_latency_ms']['p95'])

    def test_failures_not_benchmarked_as_success(self):
        r = read_benchmark(Device(fail=True), size=4096, sector=512,
                           samples=8, chunk=512, max_errors=2, timer=FakeClock())
        self.assertEqual(r['status'], 'aborted_error_limit')
        self.assertEqual(r['readable_bytes'], 512)
        self.assertEqual(r['read_errors'], 2)

    def test_large_full_scan_uses_fixed_latency_sample_cap(self):
        r = read_benchmark(Device(), size=512*9000, sector=512,
                           mode='full', chunk=512, timer=FakeClock())
        self.assertEqual(r['status'], 'completed')
        self.assertLessEqual(r['latency_sample_count'], 8192)

if __name__ == '__main__':
    unittest.main()

class ComparisonTests(unittest.TestCase):
    def test_fingerprint_mismatch_rejected(self):
        from driverepair_desktop.benchmark import compare_benchmarks
        before = {'status': 'completed', 'read_errors': 0, 'source_fingerprint': 'A',
                  'device_size_bytes': 1, 'mode': 'sample', 'requested_bytes': 2,
                  'throughput_mib_s': 100, 'read_latency_ms': {'p95': 10}}
        after = {**before, 'source_fingerprint': 'B'}
        with self.assertRaises(ValueError):
            compare_benchmarks(before, after)

    def test_reports_change_without_claiming_health(self):
        from driverepair_desktop.benchmark import compare_benchmarks
        before = {'status': 'completed', 'read_errors': 0, 'source_fingerprint': 'A',
                  'device_size_bytes': 1, 'mode': 'sample', 'requested_bytes': 2,
                  'throughput_mib_s': 100, 'read_latency_ms': {'p95': 10}}
        after = {**before, 'throughput_mib_s': 125, 'read_latency_ms': {'p95': 8}}
        result = compare_benchmarks(before, after)
        self.assertEqual(result['read_throughput_change_percent'], 25.0)
        self.assertEqual(result['p95_read_latency_change_percent'], -20.0)
        self.assertEqual(result['status'], 'comparison_only')
