"""Read-only USB disconnect/resume and honest live-rate regression cases."""
import errno
import os
from pathlib import Path
import tempfile
import unittest

from driverepair_desktop.adaptive_scan import adaptive_full_scan, classify_error
from driverepair_desktop.scan_checkpoint import ScanCheckpoint, load
from driverepair_desktop.rates import RateWindow
from driverepair_desktop.qtgui import cli_prefix, display_size
from driverepair_desktop.devices import Device


class SyntheticReader:
    def __init__(self, data, failure=None):
        self.data = data
        self.failure = failure
        self.reads = []
        self.writes = 0
    def read_at(self, offset, count):
        self.reads.append((offset, count))
        if offset == self.failure:
            ex = OSError(errno.EIO, 'USB device was unplugged')
            ex.winerror = 433
            raise ex
        return self.data[offset:offset+count]


class ResumeTests(unittest.TestCase):
    def test_cross_port_scan_identity_does_not_grant_write_identity(self):
        a=Device('windows:PhysicalDrive2','\\\\.\\PhysicalDrive2','Example HDD',
                 1000000000000,512,'usb','SERIALABC001')
        b=Device('windows:PhysicalDrive5','\\\\.\\PhysicalDrive5','Example HDD',
                 1000000000000,512,'usb','SERIALABC001')
        c=Device('windows:PhysicalDrive5','\\\\.\\PhysicalDrive5','Example HDD',
                 1000000000000,512,'usb','SERIALABC002')
        self.assertEqual(a.scan_resume_identity,b.scan_resume_identity)
        self.assertNotEqual(a.fingerprint,b.fingerprint)
        self.assertNotEqual(a.scan_resume_identity,c.scan_resume_identity)
        self.assertIsNone(Device(a.id,a.path,a.model,a.size_bytes,a.sector_size,a.bus,'').scan_resume_identity)

    def test_unplug_is_not_interpreted_as_bad_platter(self):
        ex = OSError(errno.EIO, 'device missing')
        ex.winerror = 433
        self.assertEqual(classify_error(ex), 'device_or_access_unavailable')

    def test_checkpoint_resume_does_not_repeat_earlier_blocks_or_write(self):
        data = b'X'*65536
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'checkpoint.json'
            cp = ScanCheckpoint(path, source_token='digest', size=len(data), sector=512, minimum_interval=0)
            a = SyntheticReader(data, failure=8192)
            original = adaptive_full_scan(a, size=len(data), sector=512,
                      chunk=4096, min_chunk=4096, max_chunk=4096,
                      checkpoint=cp.save, max_errors=16, max_followup_reads=8)
            self.assertEqual(original['status'], 'aborted_device_or_access_error')
            self.assertEqual(original['resume_position_bytes'], 8192)
            state = load(path, source_token='digest', size=len(data), sector=512)
            b = SyntheticReader(data)
            resumed = adaptive_full_scan(b, size=len(data), sector=512,
                      chunk=4096, min_chunk=4096, max_chunk=4096,
                      resume_state=state, checkpoint=cp.save,
                      max_errors=16, max_followup_reads=8)
            self.assertEqual(b.reads[0][0], 8192)
            self.assertEqual(resumed['resumed_from_bytes'], 8192)
            self.assertEqual(resumed['resume_position_bytes'], len(data))
            self.assertEqual(resumed['readable_bytes'], len(data))
            self.assertEqual(a.writes+b.writes, 0)
            self.assertTrue(path.exists())
            with self.assertRaisesRegex(ValueError, 'does not match'):
                load(path, source_token='different-device', size=len(data), sector=512)

    def test_invalid_checkpoint_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            cp=ScanCheckpoint(Path(folder)/'state.json',source_token='a',size=4096,sector=512)
            cp.save({'position':4097,'checked':0,'readable':0,'read_count':0,
                     'failures':0,'deferred':[], 'slow':[], 'skipped':[]},force=True)
            with self.assertRaisesRegex(ValueError, 'unaligned'):
                load(cp.path,source_token='a',size=4096,sector=512)

    def test_rate_window_is_not_whole_job_average(self):
        meter=RateWindow(seconds=3)
        self.assertIsNone(meter.update(0, now=0))
        self.assertAlmostEqual(meter.update(100, now=1), 100)
        self.assertAlmostEqual(meter.update(150, now=2), 75)
        self.assertAlmostEqual(meter.update(650, now=4), 550/3)
        self.assertAlmostEqual(meter.update(650, now=5), 500/3)

    def test_qt_helpers_are_dependency_free(self):
        self.assertIn('MiB',display_size(1048576))
        self.assertTrue(cli_prefix())

if __name__=='__main__': unittest.main()
