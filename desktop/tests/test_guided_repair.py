"""Guided scan-to-refresh: synthetic-only, no physical hardware access."""
import contextlib
import errno
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from driverepair_desktop.guided_repair import plan_targeted_refresh, tuned_scan
from driverepair_desktop.media_refresh import refresh_media
from driverepair_desktop.cli import run


class MemoryMedia:
    def __init__(self, length):
        self.data = bytearray(b'X' * length)
        self.writes = []
        self.fail_once = False
    def read_at(self, offset, count):
        return bytes(self.data[offset:offset+count])
    def write_at(self, offset, data):
        self.writes.append((offset, len(data)))
        if self.fail_once:
            self.fail_once = False
            self.data[offset:offset+len(data)//2] = data[:len(data)//2]
            raise OSError(errno.EIO, 'injected torn write')
        self.data[offset:offset+len(data)] = data
        return len(data)
    def flush(self): pass
    def close(self): pass


def scan(**overrides):
    out = {'status': 'completed_with_slow_regions', 'mode': 'triage',
           'device_size_bytes': 4096, 'read_error_chunks': 0,
           'slow_regions': [{'offset': 1024, 'length': 1024, 'latency_ms': 200}],
           'inconsistent_reads': [], 'repeat_probe_failures': 0}
    out.update(overrides)
    return out


class GuidedPlanningTests(unittest.TestCase):
    def test_autotune_is_bounded_for_large_disk(self):
        x = tuned_scan(size=12 * 10**12, sector=4096, mode='quick', bus='usb')
        self.assertEqual(x['mode'], 'triage')
        self.assertGreater(x['samples'], 256)
        self.assertGreaterEqual(x['samples'] * x['chunk'], 0.10 * 12 * 10**12)
        self.assertLessEqual(x['samples'], 100000)
        self.assertEqual(x['chunk'] % 4096, 0)
        self.assertGreaterEqual(tuned_scan(size=12 * 10**12, sector=512, mode='full')['chunk'], 1024*1024)

    def test_candidates_only_slow_readable_ranges(self):
        p = plan_targeted_refresh(scan(), sector=512, chunk=1024)
        self.assertEqual(p['targets'], [(1024, 1024)])
        self.assertEqual(p['status'], 'candidates_found')

    def test_unreadable_or_inconsistent_never_rewritten(self):
        for payload in (scan(status='completed_with_read_errors', read_error_chunks=1),
                        scan(inconsistent_reads=[{'offset': 1024}]),
                        scan(status='aborted_device_or_access_error')):
            p = plan_targeted_refresh(payload, sector=512, chunk=1024)
            self.assertEqual(p['status'], 'blocked')
            self.assertEqual(p['targets'], [])

    def test_smart_unknown_requires_separate_ack(self):
        self.assertEqual(plan_targeted_refresh(scan(), sector=512, chunk=1024,
                         hardware=True)['status'], 'blocked')
        # Consent to unknown HEALTH cannot establish the underlying medium.
        self.assertEqual(plan_targeted_refresh(scan(), sector=512, chunk=1024,
                         hardware=True, allow_unknown_health=True)['status'], 'blocked')
        # Only a separately established HDD type may reach the candidate stage.
        snapshot = {'reported_medium': 'hdd', 'status': 'unknown'}
        self.assertEqual(plan_targeted_refresh(scan(), sector=512, chunk=1024,
                         hardware=True, smart=snapshot,
                         allow_unknown_health=True)['status'], 'candidates_found')

    def test_smart_warning_still_blocks_with_unknown_override(self):
        snap = {'status':'failure_reported'}
        x = plan_targeted_refresh(scan(), sector=512, chunk=1024,
                                  hardware=True, smart=snap, allow_unknown_health=True)
        self.assertEqual(x['status'], 'blocked')

    def test_over_budget_creates_explicit_incremental_batch(self):
        s = scan(slow_regions=[{'offset': i * 512, 'latency_ms': 100} for i in range(5)])
        self.assertEqual(plan_targeted_refresh(s, sector=512, chunk=512,
                         max_regions=2)['status'], 'partial_candidates_with_unresolved_data')


class TargetedJournalTests(unittest.TestCase):
    def test_only_selected_region_written_and_verified(self):
        with tempfile.TemporaryDirectory() as td:
            media = MemoryMedia(4096)
            result = refresh_media(media, size=4096, sector=512, source_token='fileid',
                                   journal=os.path.join(td,'j'), chunk=1024, mode='targeted',
                                   targets=[(1024,1024)])
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(media.writes, [(1024,1024)])
            self.assertEqual(result['verified_bytes'], 1024)
            self.assertEqual(media.data, b'X' * 4096)

    def test_torn_write_persists_journal_and_resumes(self):
        with tempfile.TemporaryDirectory() as td:
            media = MemoryMedia(4096)
            media.fail_once = True
            journal = os.path.join(td, 'j')
            result = refresh_media(media, size=4096, sector=512, source_token='fileid',
                                   journal=journal, chunk=1024, mode='targeted', targets=[(1024,1024)])
            self.assertEqual(result['status'], 'aborted_write_or_verify_error')
            self.assertTrue(os.path.isfile(os.path.join(journal,'region.bin')))
            resumed = refresh_media(media, size=4096, sector=512, source_token='fileid',
                                    journal=journal, chunk=1024, mode='targeted', resume=True)
            self.assertEqual(resumed['status'], 'completed')
            self.assertEqual(media.data, b'X' * 4096)

    def test_bad_target_fails_before_writes(self):
        with tempfile.TemporaryDirectory() as td:
            for targets in ([(-512,512)], [(512,512),(512,512)], [(3584,1024)], [(1,512)]):
                media = MemoryMedia(4096)
                with self.assertRaises(ValueError):
                    refresh_media(media, size=4096, sector=512, source_token='id',
                                  journal=os.path.join(td,'j'), chunk=1024,
                                  mode='targeted', targets=targets)
                self.assertEqual(media.writes, [])

    def test_target_mismatch_refused_on_resume(self):
        with tempfile.TemporaryDirectory() as td:
            media = MemoryMedia(4096)
            journal=os.path.join(td,'j')
            refresh_media(media,size=4096, sector=512, source_token='id',journal=journal,
                          chunk=1024, mode='targeted',targets=[(1024,1024)])
            with self.assertRaises(RuntimeError):
                refresh_media(media,size=4096, sector=512, source_token='id',journal=journal,
                              chunk=1024,mode='targeted',resume=True,targets=[(0,1024)])


class GuidedCLIIntegrationTests(unittest.TestCase):
    acks=['--ack-risk','--ack-destructive','--ack-no-backup','--ack-data-loss-risk']

    def test_guided_image_rewrites_only_detected_regions(self):
        with tempfile.TemporaryDirectory() as td:
            image = os.path.join(td,'sample.img')
            with open(image,'wb') as f:
                f.write(b'Z' * (1024*1024))
            s = scan(device_size_bytes=1024*1024, slow_regions=[{'offset':0,'latency_ms':300}])
            with mock.patch('driverepair_desktop.cli.scan_reader', return_value=s):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = run(['care-image','--image',image,'--journal',os.path.join(td,'journal'),
                                '--json',*self.acks])
            self.assertEqual(code,0)
            data=json.loads(output.getvalue())
            self.assertEqual(data['status'],'completed_targeted_refresh')
            self.assertEqual(data['repair']['verified_bytes'],1024*1024)
            with open(image,'rb') as f:
                self.assertEqual(f.read(),b'Z'*(1024*1024))

    def test_error_scan_never_creates_write_journal(self):
        with tempfile.TemporaryDirectory() as td:
            image=os.path.join(td,'s.img')
            with open(image,'wb') as f:
                f.write(b'Z'*4096)
            journal=os.path.join(td,'journal')
            with mock.patch('driverepair_desktop.cli.scan_reader',return_value=scan(
                    device_size_bytes=4096, status='completed_with_read_errors',read_error_chunks=1)):
                out=io.StringIO()
                with contextlib.redirect_stdout(out):
                    code=run(['care-image','--image',image,'--journal',journal,'--json',*self.acks])
            self.assertEqual(code,2)
            self.assertEqual(json.loads(out.getvalue())['status'],'recovery_required')
            self.assertFalse(os.path.exists(journal))

    def test_no_suspects_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            image=os.path.join(td,'s.img')
            with open(image,'wb') as f:
                f.write(b'Z'*4096)
            journal=os.path.join(td,'journal')
            out=io.StringIO()
            with contextlib.redirect_stdout(out):
                code=run(['care-image','--image',image,'--journal',journal,'--json',*self.acks])
            self.assertEqual(code,0)
            self.assertEqual(json.loads(out.getvalue())['status'],'completed_no_refresh_needed')
            self.assertFalse(os.path.exists(journal))

    def test_physical_requires_explicit_confirmations(self):
        from driverepair_desktop.devices import Device
        d=Device('linux:/dev/sdb','/dev/sdb','Fake',4096,512,'usb','abc')
        with mock.patch('driverepair_desktop.cli.select_external_device', return_value=d):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(run(['care-external','--device',d.id,'--journal','/tmp/new']),1)
