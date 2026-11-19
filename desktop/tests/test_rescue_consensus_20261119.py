"""Rescue imaging must use the consensus engine it already ships.

Competitive review (2026-11-19) finding #1: marginal-but-readable sectors were
declared missing because the imaging path never tried shifted rereads, even
though surface_recovery.consensus_read already exists.

The first pass records failures at chunk granularity and the retry pass splits
them down to sectors - that is where shifted rereads can salvage data.
"""
import errno
import os
import tempfile
import unittest

from driverepair_desktop.recovery import rescue_reader

SECTOR = 512


class ServoReader:
    """Every 4th sector start fails when read aligned.

    Models a marginal servo/head condition: the aligned read fails, but reads
    shifted by one or two sectors return real data, so a majority vote across
    shifted attempts can still recover the sector.
    """

    def __init__(self, data, *, fail_period=4, sector=SECTOR, enabled=True):
        self.data = data
        self.fail_period = fail_period
        self.sector = sector
        self.enabled = enabled
        self.reads = []

    def read_at(self, offset, count):
        self.reads.append((offset, count))
        if self.enabled and offset % (self.sector * 4) == 0:
            raise OSError(errno.EIO, 'aligned read failed')
        return self.data[offset:offset + count]

    def close(self):
        pass


class RescueConsensusTests(unittest.TestCase):
    def setUp(self):
        self.raw = bytes((index * 5) & 0xFF for index in range(8 * 4096))
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.out = os.path.join(self.dir.name, 'rescue.img')

    def run_rescue(self, reader, **kw):
        return rescue_reader(reader, size=len(self.raw), sector=SECTOR,
                             output=self.out, source_token='consensus-token',
                             chunk=4096, max_failed_reads=8192, **kw)

    def read_image(self):
        with open(self.out, 'rb') as handle:
            return handle.read()

    def test_retry_pass_salvages_marginal_sectors_by_consensus(self):
        self.run_rescue(ServoReader(self.raw))
        state = self.run_rescue(ServoReader(self.raw), resume=True, retry_missing=True)
        self.assertGreater(state.get('consensus_recovered_bytes', 0), 0,
                           'shifted rereads should have salvaged aligned-only failures')
        self.assertTrue(state.get('consensus_recovered_ranges'))
        # Offset 0 has no earlier start to shift to, so the first sector is the
        # one range consensus genuinely cannot rescue. Everything after it can.
        self.assertEqual(state['missing_ranges'], [[0, SECTOR]])
        image = self.read_image()
        self.assertEqual(image[SECTOR:], self.raw[SECTOR:])

    def test_consensus_can_be_disabled_and_then_data_stays_missing(self):
        self.run_rescue(ServoReader(self.raw))
        state = self.run_rescue(ServoReader(self.raw), resume=True,
                                retry_missing=True, consensus_attempts=0)
        self.assertEqual(state.get('consensus_recovered_bytes', 0), 0)
        self.assertTrue(state['missing_ranges'],
                        'without consensus the unreadable sectors stay missing')
        self.assertNotEqual(self.read_image(), self.raw)

    def test_salvage_budget_is_bounded(self):
        self.run_rescue(ServoReader(self.raw))
        state = self.run_rescue(ServoReader(self.raw), resume=True,
                                retry_missing=True, consensus_sector_budget=2)
        self.assertLessEqual(len(state.get('consensus_recovered_ranges', [])), 2)

    def test_clean_media_never_uses_consensus(self):
        class Clean:
            def __init__(self, data):
                self.data = data

            def read_at(self, offset, count):
                return self.data[offset:offset + count]

            def close(self):
                pass

        state = self.run_rescue(Clean(self.raw))
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(state.get('consensus_recovered_bytes', 0), 0)
        self.assertEqual(self.read_image(), self.raw)


if __name__ == '__main__':
    unittest.main()
