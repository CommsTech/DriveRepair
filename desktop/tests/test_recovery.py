import errno
import json
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from driverepair_desktop.recovery import (
    _RESCUE_JOURNAL_CHECKPOINT_CHUNKS,
    _extend_missing_ranges,
    _merge_ranges,
    _merge_sorted_range_lists,
    rescue_reader,
)


class PatternReader:
    def __init__(self, content: bytes, bad=None):
        self.data = content
        self.bad = set(bad or [])
        self.reads = []
    def read_at(self, offset, count):
        self.reads.append((offset, count))
        if any((p >= offset and p < offset + count) for p in self.bad):
            raise OSError(errno.EIO, 'Injected bad sector')
        return self.data[offset:offset + count]
    def close(self):
        pass


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = os.path.join(self.temp.name, 'rescue.img')
        self.raw = bytes((i % 251 for i in range(8192)))

    def recover(self, reader, **kw):
        return rescue_reader(reader, size=len(self.raw), sector=512,
                             output=self.out, source_token='test-token-alpha',
                             chunk=1024, **kw)

    def test_clean_byte_exact_and_complete(self):
        state = self.recover(PatternReader(self.raw))
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(state['recovered_bytes'], len(self.raw))
        self.assertEqual(Path(self.out).read_bytes(), self.raw)
        self.assertEqual(json.loads(Path(self.out + '.rescue.json').read_text())['missing_ranges'], [])

    def test_failing_sector_is_sparse_and_marked_missing(self):
        state = self.recover(PatternReader(self.raw, bad=[1024]))
        self.assertEqual(state['status'], 'completed_with_missing_data')
        self.assertEqual(state['missing_ranges'], [[1024, 1024]])
        self.assertEqual(state['recovered_bytes'], len(self.raw) - 1024)
        result = Path(self.out).read_bytes()
        self.assertEqual(result[:1024], self.raw[:1024])
        self.assertEqual(result[1024:2048], b'\0' * 1024)
        self.assertEqual(result[2048:], self.raw[2048:])

    def test_progress_and_resume(self):
        state = self.recover(PatternReader(self.raw), max_chunks=2)
        self.assertEqual(state['status'], 'in_progress')
        self.assertEqual(state['cursor'], 2048)
        state = self.recover(PatternReader(self.raw), resume=True)
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(Path(self.out).read_bytes(), self.raw)

    def test_replaced_same_size_image_rejected_by_resume_and_status(self):
        from driverepair_desktop.recovery import inspect_rescue_status
        self.recover(PatternReader(self.raw), max_chunks=1)
        journal = Path(self.out + '.rescue.json')
        before = journal.read_bytes()
        replacement = Path(self.temp.name) / 'replacement'
        replacement.write_bytes(b'Z' * len(self.raw))
        os.replace(replacement, self.out)
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            self.recover(PatternReader(self.raw), resume=True)
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            inspect_rescue_status(self.out)
        self.assertEqual(journal.read_bytes(), before)
        self.assertEqual(Path(self.out).read_bytes(), b'Z' * len(self.raw))

    def test_legacy_journal_is_rejected_without_modification(self):
        from driverepair_desktop.recovery import inspect_rescue_status
        self.recover(PatternReader(self.raw), max_chunks=1)
        journal = Path(self.out + '.rescue.json')
        state = json.loads(journal.read_text())
        del state['output_identity']
        journal.write_text(json.dumps(state))
        before = journal.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'Legacy'):
            self.recover(PatternReader(self.raw), resume=True)
        with self.assertRaisesRegex(RuntimeError, 'Legacy'):
            inspect_rescue_status(self.out)
        self.assertEqual(journal.read_bytes(), before)

    def test_targeted_retry_repairs_previous_hole_in_image(self):
        first = self.recover(PatternReader(self.raw, bad=[1024]))
        self.assertTrue(first['missing_ranges'])
        second = self.recover(PatternReader(self.raw), resume=True, retry_missing=True)
        self.assertEqual(second['status'], 'completed')
        self.assertEqual(second['missing_ranges'], [])
        self.assertEqual(second['recovered_bytes'], len(self.raw))
        self.assertEqual(Path(self.out).read_bytes(), self.raw)

    def test_interrupted_retry_resume_keeps_pending(self):
        self.recover(PatternReader(self.raw, bad=[1024, 4096]))
        state = self.recover(PatternReader(self.raw), resume=True,
                             retry_missing=True, max_chunks=1)
        self.assertEqual(state['status'], 'retry_in_progress')
        self.assertEqual(state['retry_pending_ranges'], [[4096, 1024]])
        state = self.recover(PatternReader(self.raw), resume=True, retry_missing=True)
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(Path(self.out).read_bytes(), self.raw)

    def test_invalid_resume_source_is_rejected(self):
        self.recover(PatternReader(self.raw), max_chunks=1)
        with self.assertRaises(RuntimeError):
            rescue_reader(PatternReader(self.raw), size=len(self.raw), sector=512,
                          output=self.out, source_token='test-token-beta',
                          chunk=1024, resume=True)

    def test_invalid_journal_accounting_rejected(self):
        self.recover(PatternReader(self.raw), max_chunks=1)
        statepath = self.out + '.rescue.json'
        s = json.loads(Path(statepath).read_text())
        s['recovered_bytes'] = 999999
        with open(statepath, 'w') as f:
            json.dump(s, f)
        with self.assertRaises(ValueError):
            self.recover(PatternReader(self.raw), resume=True)

    def test_destination_write_failure_never_becomes_read_error(self):
        def failed_write(fd, data, offset):
            raise OSError(errno.ENOSPC, 'Target full')
        with patch('driverepair_desktop.recovery.pwrite', side_effect=failed_write):
            with self.assertRaises(OSError):
                self.recover(PatternReader(self.raw))
        s = json.loads(Path(self.out + '.rescue.json').read_text())
        self.assertEqual(s['cursor'], 0)
        self.assertEqual(s['recovered_bytes'], 0)

    def test_refuse_existing_output(self):
        with open(self.out, 'wb') as f:
            f.write(b'keep')
        with self.assertRaises(FileExistsError):
            self.recover(PatternReader(self.raw))
        self.assertEqual(Path(self.out).read_bytes(), b'keep')

    def test_fatal_read_errors_not_mapped_as_bad_sectors(self):
        class Gone(PatternReader):
            def read_at(self, offset, count):
                raise OSError(errno.ENODEV, 'Disconnected')
        with self.assertRaises(OSError):
            self.recover(Gone(self.raw))
        s = json.loads(Path(self.out + '.rescue.json').read_text())
        self.assertEqual(s['cursor'], 0)

    @unittest.skipUnless(os.name == 'nt', 'Windows sparse preallocation behavior')
    def test_windows_new_image_is_sparse_before_full_size_truncate(self):
        import subprocess
        import time
        size = 64 * 1024 * 1024
        data = b'\x5a' * 4096
        reader = PatternReader(data + (b'\0' * (size - len(data))))
        # Only copy the first chunk; logical image size remains large.
        t0 = time.perf_counter()
        state = rescue_reader(
            reader, size=size, sector=512, output=self.out,
            source_token='test-token-sparse', chunk=4096, max_chunks=1,
        )
        self.assertLess(time.perf_counter() - t0, 5.0)
        self.assertEqual(state['status'], 'in_progress')
        self.assertEqual(state['cursor'], 4096)
        self.assertEqual(os.path.getsize(self.out), size)
        probe = subprocess.run(
            ['fsutil', 'sparse', 'queryflag', self.out],
            capture_output=True, text=True, check=False,
        )
        self.assertIn('is set as sparse', (probe.stdout + probe.stderr).lower())

    @unittest.skipUnless(os.name == 'nt', 'Windows sparse multi-TB sizing')
    def test_windows_sparse_resize_does_not_zero_fill_large_eof(self):
        import subprocess
        import time
        from driverepair_desktop.recovery import _windows_sparse_resize
        path = os.path.join(self.temp.name, 'huge_sparse.img')
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_BINARY, 0o600)
        try:
            size = 1000204886016  # ~931 GiB Seagate-class logical size
            t0 = time.perf_counter()
            _windows_sparse_resize(fd, size)
            elapsed = time.perf_counter() - t0
        finally:
            os.close(fd)
        self.assertLess(elapsed, 2.0, f'sparse resize took {elapsed:.2f}s')
        self.assertEqual(os.path.getsize(path), size)
        probe = subprocess.run(
            ['fsutil', 'sparse', 'queryflag', path],
            capture_output=True, text=True, check=False,
        )
        self.assertIn('is set as sparse', (probe.stdout + probe.stderr).lower())
        # Valid data length must stay tiny — not a multi-GB zero-fill.
        vdl = subprocess.run(
            ['fsutil', 'file', 'queryvaliddata', path],
            capture_output=True, text=True, check=False,
        )
        combined = (vdl.stdout + vdl.stderr).lower()
        self.assertTrue(
            '0x0' in combined or '(0)' in combined.replace(' ', ''),
            msg=combined,
        )

    def test_extend_missing_ranges_coalesces_without_resort_of_history(self):
        # 4096 already-sorted fragmented holes; append adjacent/overlapping additions.
        accumulated = [[i * 4096, 512] for i in range(4096)]
        added = [[0, 512], [512, 512], [4096 * 4095 + 512, 512]]
        merged = _extend_missing_ranges(accumulated, added)
        # Adjacent add at 512 coalesces into the first hole; last hole grows.
        self.assertEqual(merged[0], [0, 1024])
        self.assertEqual(merged[-1], [4096 * 4095, 1024])
        self.assertEqual(len(merged), 4096)
        # Same result as full re-merge, without requiring a full historical sort.
        self.assertEqual(merged, _merge_ranges(accumulated + added))
        again = _merge_sorted_range_lists(merged, [])
        self.assertIs(again, merged)

    def test_journal_checkpoint_batches_fsync_but_forces_on_stop(self):
        fsync_calls = {'n': 0}
        real_fsync = os.fsync

        def counting_fsync(fd):
            fsync_calls['n'] += 1
            return real_fsync(fd)

        chunks = _RESCUE_JOURNAL_CHECKPOINT_CHUNKS * 2 + 3  # 35 chunks
        payload = self.raw * 8  # 64 KiB → 64 × 1 KiB chunks available
        with patch('driverepair_desktop.recovery.os.fsync', side_effect=counting_fsync):
            state = rescue_reader(
                PatternReader(payload), size=len(payload), sector=512,
                output=self.out, source_token='test-token-alpha', chunk=1024,
                max_chunks=chunks,
            )
        self.assertEqual(state['status'], 'in_progress')
        self.assertEqual(state['cursor'], chunks * 1024)
        # Old path fsynced image + journal (~2+) every chunk. Batched path must
        # be far lower while still forcing a final/stop checkpoint.
        self.assertGreaterEqual(fsync_calls['n'], 2)
        self.assertLess(fsync_calls['n'], chunks * 2)


if __name__ == '__main__':
    unittest.main()
