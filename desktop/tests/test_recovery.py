import errno
import json
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from driverepair_desktop.recovery import rescue_reader


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

if __name__ == '__main__':
    unittest.main()
