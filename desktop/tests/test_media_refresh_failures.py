"""Fault injection for the rolling journal. Never opens raw disks."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from driverepair_desktop.cli import _refresh_image_token, run
from driverepair_desktop.media_refresh import (
    ImageReadWriter, STATE_COMMITTED, STATE_VERIFIED, _atomic_write_bytes,
    _default_meta, _sha256, refresh_media,
)
from driverepair_desktop.recovery import _state_save


class FaultTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.patient = Path(self.t.name) / 'disk.img'
        self.original = bytes((i * 13 + 7) % 256 for i in range(8192))
        self.patient.write_bytes(self.original)
        self.journal = str(Path(self.t.name) / 'safe-journal')

    def call(self, media, *, resume=False, mode='full', **kw):
        return refresh_media(
            media, size=len(self.original), sector=512, source_token='stable',
            journal=self.journal, chunk=1024, mode=mode, resume=resume,
            journal_backend='disk', auto_escalate=False,
            adaptive_samples=8, slow_multiplier=1.2, **kw,
        )

    def test_torn_write_keeps_original_in_disk_journal_until_resume(self):
        class FailingWrite(ImageReadWriter):
            def __init__(self, path):
                super().__init__(path)
                self.fail_once = True

            def write_at(self, offset, data):
                if self.fail_once:
                    self.fail_once = False
                    super().write_at(offset, b'BAD!' + data[4:128])
                    raise OSError(5, 'simulated torn write')
                return super().write_at(offset, data)

        media = FailingWrite(str(self.patient))
        try:
            result = self.call(media)
        finally:
            media.close()
        self.assertEqual(result['status'], 'aborted_write_or_verify_error')
        self.assertEqual(result['transaction']['state'], 'WRITING')
        self.assertTrue((Path(self.journal) / 'region.bin').is_file())
        self.assertEqual((Path(self.journal) / 'region.bin').read_bytes(), self.original[:1024])
        self.assertNotEqual(self.patient.read_bytes(), self.original)

        media = ImageReadWriter(str(self.patient))
        try:
            done = self.call(media, resume=True)
        finally:
            media.close()
        self.assertEqual(done['status'], 'completed')
        self.assertEqual(done['rewritten_bytes'], len(self.original))
        self.assertEqual(self.patient.read_bytes(), self.original)

    def test_write_failure_does_not_erase_journal_even_after_repeated_fail(self):
        class Unwritable(ImageReadWriter):
            def write_at(self, offset, data):
                raise OSError(5, 'write rejected')
        media = Unwritable(str(self.patient))
        try:
            result = self.call(media)
        finally:
            media.close()
        self.assertEqual(result['status'], 'aborted_write_or_verify_error')
        self.assertEqual(result['rewritten_bytes'], 0)
        self.assertTrue((Path(self.journal) / 'region.bin').is_file())

    def test_postwrite_readback_failure_keeps_journal(self):
        class UnreadableAfterWrite(ImageReadWriter):
            def __init__(self, path):
                super().__init__(path)
                self.did_write = False
            def write_at(self, offset, data):
                self.did_write = True
                return super().write_at(offset, data)
            def read_at(self, offset, count):
                if self.did_write:
                    raise OSError(5, 'read-back failed')
                return super().read_at(offset, count)
        media = UnreadableAfterWrite(str(self.patient))
        try:
            result = self.call(media)
        finally:
            media.close()
        self.assertEqual(result['status'], 'aborted_write_or_verify_error')
        self.assertTrue((Path(self.journal) / 'region.bin').is_file())
        self.assertIsNotNone(result['transaction'])
        media = ImageReadWriter(str(self.patient))
        try:
            done = self.call(media, resume=True)
        finally:
            media.close()
        self.assertEqual(done['status'], 'completed')
        self.assertEqual(self.patient.read_bytes(), self.original)

    def test_verified_state_commits_once_after_crash(self):
        os.mkdir(self.journal)
        _atomic_write_bytes(str(Path(self.journal) / 'region.bin'), self.original[:1024])
        meta = _default_meta(source_token='stable', size=len(self.original),
                             sector=512, chunk=1024, mode='full',
                             verify=True, consistency_reads=2)
        meta['journal_backend'] = 'disk'
        meta['queue'] = None
        meta['transaction'] = dict(state=STATE_VERIFIED, offset=0, length=1024,
                                   sha256=_sha256(self.original[:1024]))
        _state_save(str(Path(self.journal) / 'meta.json'), meta)
        media = ImageReadWriter(str(self.patient))
        try:
            done = self.call(media, resume=True)
        finally:
            media.close()
        self.assertEqual(done['status'], 'completed')
        self.assertEqual(done['rewritten_bytes'], len(self.original))
        self.assertEqual(done['verified_bytes'], len(self.original))

    def test_committed_state_does_not_double_count(self):
        os.mkdir(self.journal)
        meta = _default_meta(source_token='stable', size=len(self.original),
                             sector=512, chunk=1024, mode='full',
                             verify=True, consistency_reads=2)
        meta['journal_backend'] = 'disk'
        meta['queue'] = None
        meta['cursor'] = 1024
        meta['rewritten_bytes'] = 1024
        meta['verified_bytes'] = 1024
        meta['transaction'] = dict(state=STATE_COMMITTED, offset=0, length=1024,
                                   sha256=_sha256(self.original[:1024]))
        _state_save(str(Path(self.journal) / 'meta.json'), meta)
        media = ImageReadWriter(str(self.patient))
        try:
            done = self.call(media, resume=True)
        finally:
            media.close()
        self.assertEqual(done['rewritten_bytes'], len(self.original))

    def test_adaptive_queue_survives_failure_and_resume(self):
        class SlowSpot(ImageReadWriter):
            def __init__(self, path, fail=False):
                super().__init__(path)
                self.fail = fail
            def read_at(self, offset, count):
                if offset == 4096:
                    time.sleep(.006)
                return super().read_at(offset, count)
            def write_at(self, offset, data):
                if self.fail:
                    raise OSError(5, 'injected')
                return super().write_at(offset, data)
        media = SlowSpot(str(self.patient), fail=True)
        try:
            result = self.call(media, mode='adaptive')
        finally:
            media.close()
        self.assertEqual(result['status'], 'aborted_write_or_verify_error')
        self.assertGreater(result['queue_remaining'], 0)
        first = result['transaction']['offset']
        meta = json.loads((Path(self.journal) / 'meta.json').read_text())
        self.assertEqual(meta['queue'][0][0], first)
        media = SlowSpot(str(self.patient))
        try:
            done = self.call(media, mode='adaptive', resume=True)
        finally:
            media.close()
        self.assertEqual(done['status'], 'completed')
        self.assertEqual(done['queue_remaining'], 0)
        self.assertEqual(self.patient.read_bytes(), self.original)

    def test_adaptive_probe_read_error_stops_before_any_write(self):
        class UnreadableProbe(ImageReadWriter):
            def __init__(self, path):
                super().__init__(path)
                self.write_count = 0
            def read_at(self, offset, count):
                if offset == 4096:
                    raise OSError(5, "unreadable in probe")
                return super().read_at(offset, count)
            def write_at(self, offset, data):
                self.write_count += 1
                return super().write_at(offset, data)
        media = UnreadableProbe(str(self.patient))
        try:
            result = self.call(media, mode="adaptive")
            self.assertEqual(media.write_count, 0)
        finally:
            media.close()
        self.assertEqual(result["status"], "aborted_probe_read_errors")
        self.assertEqual(self.patient.read_bytes(), self.original)

    def test_image_identity_survives_self_rewrite(self):
        before, _ = _refresh_image_token(str(self.patient))
        os.utime(self.patient, None)
        after, _ = _refresh_image_token(str(self.patient))
        self.assertEqual(before, after)

    def test_live_hybrid_rejected_before_device_selected(self):
        code = run(['refresh-external', '--device', 'unmatched',
                    '--journal', self.journal, '--journal-backend', 'hybrid'])
        self.assertEqual(code, 1)

    def test_live_no_verify_rejected_before_device_selected(self):
        code = run(['refresh-external', '--device', 'unmatched',
                    '--journal', self.journal, '--no-verify'])
        self.assertEqual(code, 1)

    def test_changed_journal_policy_rejected_on_resume(self):
        media = ImageReadWriter(str(self.patient))
        try:
            self.call(media)
        finally:
            media.close()
        media = ImageReadWriter(str(self.patient))
        try:
            with self.assertRaisesRegex(RuntimeError, 'Verification/consistency'):
                self.call(media, resume=True, verify=False)
        finally:
            media.close()


if __name__ == '__main__':
    unittest.main()
