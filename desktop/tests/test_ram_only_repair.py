"""Safe synthetic validation for no-image/no-journal in-place maintenance.

Never opens raw physical drives.
"""
import contextlib
import errno
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from driverepair_desktop.cli import run
from driverepair_desktop.media_refresh import ImageReadWriter, refresh_media


class RamOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patient = self.root / 'patient.img'
        self.raw = bytes(range(256)) * 4096
        self.patient.write_bytes(self.raw)
        self.journal = str(self.root / 'WOULD_BE_A_JOURNAL')

    def refresh(self, media, *, resume=False):
        return refresh_media(
            media, size=len(self.raw), sector=512, source_token='safe-test',
            journal=self.journal, chunk=4096, mode='targeted',
            targets=[(4096,4096)], resume=resume,
            journal_backend='memory', consistency_reads=2,
        )

    def test_memory_refresh_creates_no_journal_or_auxiliary_files(self):
        media = ImageReadWriter(str(self.patient))
        try:
            result = self.refresh(media)
        finally:
            media.close()
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['verified_bytes'], 4096)
        self.assertEqual(self.patient.read_bytes(), self.raw)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['patient.img'])
        self.assertFalse(os.path.exists(self.journal))
        self.assertFalse(result['resume_possible_after_exit'])

    def test_memory_does_not_offer_false_resume(self):
        media = ImageReadWriter(str(self.patient))
        try:
            with self.assertRaisesRegex(ValueError,'cannot resume'):
                self.refresh(media, resume=True)
        finally:
            media.close()

    def test_transient_torn_write_attempts_immediate_restore(self):
        class Once(ImageReadWriter):
            def __init__(self,p):
                super().__init__(p)
                self.once=True
            def write_at(self, offset, data):
                if self.once:
                    self.once=False
                    super().write_at(offset, b'Z'*len(data))
                    raise OSError(errno.EIO,'synthetic partial write')
                return super().write_at(offset,data)
        media = Once(str(self.patient))
        try:
            result = self.refresh(media)
        finally:
            media.close()
        self.assertEqual(result['status'],'aborted_volatile_region_restored')
        self.assertEqual(self.patient.read_bytes(), self.raw)
        self.assertFalse(os.path.exists(self.journal))

    def test_permanent_write_failure_warns_critical_and_does_not_claim_repaired(self):
        class Always(ImageReadWriter):
            def write_at(self, offset, data):
                super().write_at(offset, b'R'*len(data))
                raise OSError(errno.EIO, 'synthetic persistent failure')
        media = Always(str(self.patient))
        try:
            result = self.refresh(media)
        finally:
            media.close()
        self.assertEqual(result['status'],'critical_volatile_rollback_failed')
        self.assertEqual(result['verified_bytes'], 0)
        self.assertNotEqual(self.patient.read_bytes(),self.raw)
        self.assertFalse(os.path.exists(self.journal))

    def test_cli_whole_image_refresh_without_journal_or_destination(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run(['refresh-image','--image',str(self.patient),
                        '--journal-backend','memory','--mode','full','--chunk-mib','1',
                        '--ack-risk','--ack-destructive','--ack-no-backup',
                        '--ack-data-loss-risk','--after-run','keep','--json',
                        '--no-live-dashboard'])
        parsed=json.loads(out.getvalue())
        self.assertEqual(code,0)
        self.assertEqual(parsed['status'],'completed')
        self.assertTrue(parsed['volatile_ram_only'])
        self.assertIsNone(parsed['journal'])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['patient.img'])

    def test_guided_image_repair_creates_no_journal(self):
        # The real scan algorithm is mocked so the test exercises the GUI's
        # CLI orchestration, safety flags and exact target refresh independently
        # of machine-specific disk cache timing.
        prepared={
            'status':'completed_with_slow_regions', 'mode':'triage',
            'device_size_bytes':len(self.raw),'read_error_chunks':0,
            'inconsistent_reads':[], 'repeat_probe_failures':0,
            'slow_regions':[{'offset':0,'length':1048576,'latency_ms':200}],
        }
        out=io.StringIO()
        with mock.patch('driverepair_desktop.cli.scan_reader', return_value=prepared), contextlib.redirect_stdout(out):
            code = run(['care-image','--image',str(self.patient),
                        '--journal-backend','memory','--ack-volatile-journal',
                        '--mode','quick','--ack-risk','--ack-destructive',
                        '--ack-no-backup','--ack-data-loss-risk','--json'])
        self.assertEqual(code,0)
        parsed=json.loads(out.getvalue())
        self.assertTrue(parsed['volatile_ram_only'])
        self.assertEqual(parsed['repair']['verified_bytes'],len(self.raw))
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['patient.img'])

    def test_mock_external_ram_repair_never_creates_a_journal(self):
        from types import SimpleNamespace
        from driverepair_desktop.guided_repair import plan_targeted_refresh
        from driverepair_desktop.media_refresh import ReadWriter
        class FakeDrive:
            def __init__(self, size):
                self.raw = bytearray(b'M' * size)
                self.writes = []
            def read_at(self, offset, n):
                return bytes(self.raw[offset:offset + n])
            def write_at(self, offset, data):
                self.writes.append((offset, len(data)))
                self.raw[offset:offset + len(data)] = data
                return len(data)
            def flush(self): pass
            def close(self): pass

        size = 1024 * 1024
        disk = SimpleNamespace(id='linux:/dev/FAKE', path='/dev/FAKE',
                               model='Synthetic USB', size_bytes=size,
                               sector_size=512, serial='fake-001', bus='usb',
                               fingerprint='aabbccddeeff001122334455')
        fixture = FakeDrive(size)
        report = {
            'status':'completed_with_slow_regions', 'mode':'triage',
            'device_size_bytes':size, 'read_error_chunks':0,
            'inconsistent_reads':[], 'repeat_probe_failures':0,
            'slow_regions':[{'offset':0,'length':size,'latency_ms':120}],
        }
        from driverepair_desktop import cli
        output = io.StringIO()
        with (mock.patch.object(cli, 'select_external_device', return_value=disk),
              mock.patch.object(cli, 'list_external_devices', return_value=[disk]),
              mock.patch.object(cli, 'assert_patient_idle_windows'),
              mock.patch.object(cli, 'assert_windows_external_write_gate'),
              mock.patch.object(cli, '_verify_linux_patient_not_in_use'),
              mock.patch.object(cli, '_validate_live_refresh_preflight') as preflight,
              mock.patch.object(cli, 'open_device_readonly', return_value=fixture),
              mock.patch.object(cli, 'open_device_readwrite', return_value=fixture),
              mock.patch.object(cli, 'try_health_snapshot', return_value={'reported_medium':'hdd', 'status':'smart_passed_limited', 'source':'smartctl'}),
              mock.patch.object(cli, 'scan_reader', return_value=report),
              contextlib.redirect_stdout(output)):
            args = ['care-external', '--device', disk.id,
                    '--mode','quick', '--journal-backend','memory',
                    '--ack-volatile-journal', '--ack-risk',
                    '--ack-destructive', '--ack-no-backup',
                    '--ack-data-loss-risk', '--ack-usb-bridge-risk',
                    '--ack-unvalidated-hardware', '--ack-unknown-health',
                    '--confirm-identity', disk.fingerprint[:12], '--json']
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertNotEqual(run(args), 0)
            self.assertEqual(fixture.writes, [])
            output.seek(0)
            output.truncate()
            exit_code = run([*args, '--ack-dock-power-backed'])
        self.assertEqual(exit_code, 0)
        preflight.assert_not_called()
        self.assertEqual(fixture.writes, [(0, size)])
        result=json.loads(output.getvalue())
        self.assertEqual(result['status'], 'completed_targeted_refresh')
        self.assertTrue(result['volatile_ram_only'])
        self.assertIsNone(result['repair']['journal'])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['patient.img'])

    def test_ram_only_requires_volatile_ack_before_touching_image(self):
        with contextlib.redirect_stderr(io.StringIO()):
            code=run(['care-image','--image',str(self.patient),
                      '--journal-backend','memory','--ack-risk','--ack-destructive',
                      '--ack-no-backup','--ack-data-loss-risk'])
        self.assertNotEqual(code,0)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['patient.img'])


if __name__ == '__main__':
    unittest.main()
