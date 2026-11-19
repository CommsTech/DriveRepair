"""No physical devices. Capacity spot test, interruption journal and report contract."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from driverepair_desktop.capacity_validation import (
    RegularImageWriter, planned_locations, latency_stats, restore_pending, validate_spots)
from driverepair_desktop.drive_report import render_report, save_report
from driverepair_desktop.automatic_maintenance import choose_maintenance
from driverepair_desktop.workstation_ui import can_start, operation_impact


class CorruptingWriter:
    def __init__(self, source, *, mismatch=False, fail_restore=False):
        self.inner=source
        self.writes=0
        self.mismatch=mismatch
        self.fail_restore=fail_restore
    def read_at(self, off, n):
        return self.inner.read_at(off,n)
    def write_at(self, off, data):
        self.writes+=1
        if self.fail_restore and self.writes==2:
            raise OSError('restore denied')
        if self.mismatch and self.writes==1:
            return self.inner.write_at(off,bytes(len(data)))
        return self.inner.write_at(off,data)
    def flush(self):self.inner.flush()


class CapacityTests(unittest.TestCase):
    def test_locations_are_spaced_aligned_and_metadata_edges_untouched(self):
        size=16*1024**3
        offsets=planned_locations(size,512,samples=576)
        self.assertEqual(len(offsets),len(set(offsets)))
        self.assertGreaterEqual(offsets[0],16*1024**2)
        self.assertLessEqual(offsets[-1]+4096,size-16*1024**2)
        self.assertTrue(all(v%4096==0 for v in offsets))
        with self.assertRaises(ValueError):
            planned_locations(64*1024,512,samples=576)

    def test_success_preserves_every_original_byte_and_latency_metrics(self):
        with tempfile.TemporaryDirectory() as root:
            image=Path(root)/'patient.img'
            data=os.urandom(1024*1024)
            image.write_bytes(data)
            media=RegularImageWriter(str(image))
            try:
                result=validate_spots(media,size=media.size,sector=512,source_token=media.token,
                    journal_dir=Path(root)/'safe-journal',samples=12,skip_edges=0)
            finally:media.close()
            self.assertEqual(image.read_bytes(),data)
            self.assertEqual(result['status'],'SAMPLED_REGIONS_VERIFIED')
            self.assertEqual(result['counters']['validated'],12)
            self.assertEqual(result['read_latency']['samples'],24)
            self.assertEqual(result['write_latency']['samples'],12)
            self.assertTrue(all(x['original_restored_and_verified'] for x in result['regions']))
            self.assertIn('do not certify',str(result['notes']).lower())

    def test_alias_like_mismatch_is_not_pass_even_when_original_restored(self):
        with tempfile.TemporaryDirectory() as root:
            image=Path(root)/'fake.img';image.write_bytes(b'Z'*(512*1024))
            media=RegularImageWriter(str(image))
            try:
                result=validate_spots(CorruptingWriter(media,mismatch=True),size=media.size,
                    sector=512,source_token=media.token,journal_dir=Path(root)/'j',
                    samples=8,skip_edges=0)
            finally:media.close()
            self.assertEqual(result['counters']['mismatch'],1)
            self.assertEqual(result['status'],'CAPACITY_INTEGRITY_WARNINGS')
            self.assertEqual(image.read_bytes(),b'Z'*(512*1024))

    def test_failed_restoration_keeps_journal_and_can_be_recovered(self):
        with tempfile.TemporaryDirectory() as root:
            image=Path(root)/'fake.img';data=os.urandom(512*1024);image.write_bytes(data)
            journal=Path(root)/'journal'
            media=RegularImageWriter(str(image))
            try:
                with self.assertRaisesRegex(OSError,'CRITICAL'):
                    validate_spots(CorruptingWriter(media,fail_restore=True),size=media.size,
                        sector=512,source_token=media.token,journal_dir=journal,
                        samples=8,skip_edges=0)
                self.assertTrue((journal/'region.bin').is_file())
                state=json.loads((journal/'meta.json').read_text())
                self.assertEqual(state['state'],'RESTORE_FAILED')
                outcome=restore_pending(media,journal,source_token=media.token,
                    size=media.size,sector=512)
                self.assertEqual(outcome['status'],'ORIGINAL_RESTORED_VERIFIED')
                self.assertFalse((journal/'region.bin').exists())
            finally:media.close()
            self.assertEqual(image.read_bytes(),data)

    def test_windows_fallback_without_pread_pwrite(self):
        with tempfile.TemporaryDirectory() as root:
            image=Path(root)/'image.img';image.write_bytes(os.urandom(512*1024))
            original=image.read_bytes()
            media=RegularImageWriter(str(image))
            try:
                with mock.patch('driverepair_desktop.capacity_validation.os.pread', None,create=True), \
                     mock.patch('driverepair_desktop.capacity_validation.os.pwrite', None,create=True):
                    outcome=validate_spots(media,size=media.size,sector=512,source_token=media.token,
                        journal_dir=Path(root)/'journal',samples=8,skip_edges=0)
                self.assertEqual(outcome['status'],'SAMPLED_REGIONS_VERIFIED')
            finally:media.close()
            self.assertEqual(image.read_bytes(),original)

    def test_symlinked_journal_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            image=Path(root)/'image.img';image.write_bytes(os.urandom(512*1024))
            real=Path(root)/'real';real.mkdir()
            alias=Path(root)/'alias'
            try:alias.symlink_to(real,target_is_directory=True)
            except (OSError,NotImplementedError):self.skipTest('Host cannot create symlinks')
            media=RegularImageWriter(str(image))
            try:
                with self.assertRaises(PermissionError):
                    validate_spots(media,size=media.size,sector=512,source_token=media.token,
                        journal_dir=alias,samples=8,skip_edges=0)
            finally:media.close()

    def test_stop_between_regions_never_writes_remaining_samples(self):
        with tempfile.TemporaryDirectory() as root:
            image=Path(root)/'fake.img';image.write_bytes(b'A'*(512*1024))
            media=RegularImageWriter(str(image))
            count=[0]
            try:
                result=validate_spots(media,size=media.size,sector=512,source_token=media.token,
                    journal_dir=Path(root)/'j',samples=8,skip_edges=0,
                    stop_requested=lambda:count[0]>=3,
                    progress=lambda _:count.__setitem__(0,count[0]+1))
            finally:media.close()
            self.assertEqual(result['status'],'STOPPED_INCOMPLETE')
            self.assertEqual(result['counters']['untested'],5)
            self.assertEqual(image.read_bytes(),b'A'*(512*1024))

    def test_html_escapes_untrusted_media_and_does_not_fabricate_capacity(self):
        result={'test_kind':'capacity_spot_write_restore','status':'CAPACITY_INTEGRITY_WARNINGS',
                'declared_bytes':10**12,'samples_planned':2,'samples_completed':2,
                'counters':{'validated':1,'mismatch':1},
                'highest_verified_offset':12345,
                'regions':[{'offset':0,'length':4096,'status':'validated'},
                           {'offset':10**11,'length':4096,'status':'mismatch'}],
                'read_latency':latency_stats([1.0,2.0,3.0]),
                'write_latency':latency_stats([10.0,20.0])}
        output=render_report(result,device={'model':'<script>alert(1)</script>'})
        self.assertNotIn('<script>',output)
        self.assertIn('&lt;script&gt;',output)
        self.assertIn('Highest validated address',output)
        self.assertIn('NOT contiguous validated capacity',output)
        self.assertIn('Coefficient of variation',output)
        self.assertIn('Mismatch',output)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'report.html'
            save_report(path,result)
            with self.assertRaises(ValueError):save_report(path,result)

    def test_auto_policy_is_read_stress_selection_not_write_permission(self):
        smr=choose_maintenance(model='ST1000LM048',bus='usb',
                               snapshot={'reported_medium':'hdd'})
        self.assertEqual(smr.level,2)
        self.assertEqual(choose_maintenance(model='Disk',bus='nvme',
                            snapshot={'reported_medium':'ssd'}).level,1)
        self.assertEqual(choose_maintenance(model='ST1000LM048',bus='usb',
                            snapshot={'reported_medium':'hdd'},read_errors=22).level,1)
        allowed,note=can_start('capacity',device_selected=True,image_exists=False,
                               running=False,public_beta=True)
        self.assertFalse(allowed)
        self.assertIn('WRITE',operation_impact('capacity')[0])

    def test_public_policy_denies_in_place_image_capacity_writes(self):
        from driverepair_desktop import release_policy
        with mock.patch.object(release_policy,'PUBLIC_BETA_IMAGE_ONLY',True):
            with self.assertRaisesRegex(ValueError,'In-place patient writes'):
                release_policy.block_public_physical_writes('validate-image-capacity')

    def test_cli_image_end_to_end_detailed_report(self):
        from driverepair_desktop.cli import run
        with tempfile.TemporaryDirectory() as td:
            patient=Path(td)/'patient.img';patient.write_bytes(os.urandom(512*1024))
            report=Path(td)/'result.html'
            with mock.patch('builtins.print'):
                exitcode=run(['validate-image-capacity','--image',str(patient),
                    '--journal',str(Path(td)/'journal'),'--samples','72',
                    '--report-html',str(report),'--json'])
            self.assertEqual(exitcode,0)
            self.assertIn('Sampled address map',report.read_text())

if __name__=='__main__':unittest.main()
