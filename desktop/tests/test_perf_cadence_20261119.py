"""Performance regressions from the 2026-11-19 optimization review.

Both findings were measured by the reviewer: per-chunk recovery validation
(32 ms/call at 50k ranges) and a durable checkpoint after every adaptive scan
chunk (4.15 ms/save). The fixes keep identical durability guarantees.
"""
import errno
import os
import tempfile
import unittest
from unittest import mock

from driverepair_desktop import recovery
from driverepair_desktop.adaptive_scan import adaptive_full_scan
from driverepair_desktop.recovery import rescue_reader


class Reader:
    def __init__(self, data, bad_offsets=()):
        self.data = data
        self.bad = set(bad_offsets)
        self.reads = []

    def read_at(self, offset, count):
        self.reads.append((offset, count))
        if offset in self.bad:
            raise OSError(errno.EIO, 'injected failure')
        return self.data[offset:offset + count]

    def close(self):
        pass


class RecoveryValidationCadenceTests(unittest.TestCase):
    def test_validation_runs_at_checkpoints_not_every_chunk(self):
        data = bytes(64 * 1024)
        reader = Reader(data)
        calls = {'n': 0}
        original = recovery._validate_state

        def counting(state):
            calls['n'] += 1
            return original(state)

        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, 'rescue.img')
            with mock.patch.object(recovery, '_validate_state', side_effect=counting):
                rescue_reader(reader, size=len(data), sector=512, output=out,
                              source_token='perf-token', chunk=512)
        chunks = len(data) // 512
        self.assertGreater(chunks, recovery._RESCUE_JOURNAL_CHECKPOINT_CHUNKS)
        # Before the fix this was >= chunks (one call per chunk).
        self.assertLess(calls['n'], chunks // 4,
                        f'validation still runs per chunk: {calls["n"]} calls for {chunks} chunks')
        self.assertGreaterEqual(calls['n'], 1, 'the final durability boundary must still validate')

    def test_rescue_still_completes_and_matches_source(self):
        data = bytes((index * 7) & 0xFF for index in range(32 * 1024))
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, 'rescue.img')
            state = rescue_reader(Reader(data), size=len(data), sector=512,
                                  output=out, source_token='perf-token-2', chunk=512)
            self.assertEqual(state['status'], 'completed')
            with open(out, 'rb') as handle:
                self.assertEqual(handle.read(), data)


class AdaptiveCheckpointCadenceTests(unittest.TestCase):
    def test_checkpoints_are_throttled_but_forced_saves_survive(self):
        size = 16 * 1024 * 1024
        data = bytes(size)
        saves = []

        def checkpoint(state, *, force=False):
            saves.append((state['position'], force))

        adaptive_full_scan(Reader(data), size=size, sector=512, chunk=512 * 1024,
                           max_errors=4, checkpoint=checkpoint,
                           min_chunk=512 * 1024, max_chunk=1024 * 1024)
        chunks = size // (512 * 1024)
        self.assertGreater(chunks, 8)
        self.assertLess(len(saves), chunks,
                        f'checkpoint still writes per chunk: {len(saves)} saves for {chunks} chunks')
        self.assertTrue(any(force for _, force in saves), 'completion must force a durable save')
        self.assertEqual(saves[-1][0], size, 'final checkpoint must record the end position')

    def test_resume_from_throttled_checkpoint_still_completes(self):
        # Large enough to cross a 16-chunk checkpoint boundary mid-scan; a
        # smaller image only ever checkpoints at completion.
        size = 64 * 1024 * 1024
        data = bytes((index % 251 for index in range(1024)))
        data = data * (size // len(data))
        saved = {}
        stopped = {'done': False}

        def checkpoint(state, *, force=False):
            saved.update(state)
            if not stopped['done'] and 0 < state['position'] < size:
                stopped['done'] = True
                # Simulate the process stopping mid-scan: the durable state so
                # far is exactly what a resume would load.
                raise RuntimeError('simulated stop')

        with self.assertRaises(RuntimeError):
            adaptive_full_scan(Reader(data), size=size, sector=512, chunk=512 * 1024,
                               max_errors=4, checkpoint=checkpoint,
                               min_chunk=512 * 1024, max_chunk=512 * 1024)
        self.assertIn('position', saved)
        self.assertGreater(saved['position'], 0)
        self.assertLess(saved['position'], size)
        state = adaptive_full_scan(Reader(data), size=size, sector=512,
                                   chunk=512 * 1024, max_errors=4,
                                   checkpoint=checkpoint,
                                   resume_state=saved, min_chunk=512 * 1024,
                                   max_chunk=512 * 1024)
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(saved['position'], size, 'final forced checkpoint must reach the end')


if __name__ == '__main__':
    unittest.main()
