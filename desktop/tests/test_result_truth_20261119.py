"""User-visible results are not success claims when data is still unreadable."""
import unittest
from unittest import mock
from driverepair_desktop.workstation_ui import repair_presentation, drive_inspection_text
from driverepair_desktop.guided_repair import plan_targeted_refresh
from driverepair_desktop.qtgui import estimated_job_percent
from driverepair_desktop.media_profiles import identify_profile
from driverepair_desktop.repair_strategy import advise

class ResultTruthTests(unittest.TestCase):
    def sample(self):
        return {'status':'partial_repair_unresolved_data',
                'scan':{'read_error_chunks':248,'status':'completed_with_read_errors'},
                'repair':{'status':'completed','rewritten_bytes':6848512},
                'postverification':{'status':'postverify_passed','verified_bytes':6848512}}

    def test_partial_nonzero_is_not_generic_failure_and_not_success(self):
        outcome=repair_presentation(self.sample(),exit_code=2)
        self.assertIn('Partial',outcome.heading)
        self.assertIn('248 failed read attempts',outcome.explanation)
        self.assertIn('independently reread',outcome.explanation)
        self.assertIn('unreadable data remains',outcome.heading)
        self.assertNotIn('recovered data',outcome.explanation)
        self.assertIn('separate healthy storage',outcome.next_action)

    def test_verification_unknown_never_claims_independent_match(self):
        result=self.sample()
        result['postverification']={'status':'postverify_failed','verified_bytes':0}
        result['status']='repair_postverify_failed'
        outcome=repair_presentation(result,exit_code=2)
        self.assertIn('NOT confirmed',outcome.explanation)
        self.assertNotIn('independently reread and digest-matched',outcome.explanation)
        self.assertTrue(outcome.complete_with_unresolved)

    def test_successful_rewrite_still_not_healthy(self):
        result=self.sample()
        result['status']='completed_targeted_refresh'
        outcome=repair_presentation(result,exit_code=0)
        self.assertIn('NOT certified',outcome.heading)
        self.assertIn('Back up immediately',outcome.next_action)

    def test_missing_optional_metadata_preserves_known_inventory(self):
        record={'model':'SanDisk SDSSDH3 500G USB Device','size_bytes':500000000000,
                'bus':'usb','serial_suffix':'***0000','sector_size':512}
        body=drive_inspection_text(record,error='USB device did not answer')
        self.assertIn('SanDisk SDSSDH3',body)
        self.assertIn('500000000000',body)
        self.assertIn('Unavailable',body)
        self.assertIn('never authorizes physical writes',body)
        self.assertIn('USB device did not answer',body)
        self.assertNotIn('certified',body.lower())

    def test_inspection_whitelists_fields_and_does_not_show_serial(self):
        body=drive_inspection_text({'model':'Disk','bus':'usb'},
            {'firmware_revision':'1.2','serial':'CONFIDENTIAL','size_bytes':1024})
        self.assertIn('Firmware Revision: 1.2',body)
        self.assertNotIn('CONFIDENTIAL',body)

    def test_preverification_refresh_progress_never_claims_finished(self):
        event={'phase':'REFRESH','refresh_index':16,'refresh_total':16}
        self.assertLess(estimated_job_percent(event,guided=True),100)
        self.assertEqual(estimated_job_percent(event,guided=False),100)

    def test_sandisk_ultra_3d_model_is_ssd_advisory_not_write_permission(self):
        label='SanDisk SDSSDH3 500G USB Device'
        profile=identify_profile(model=label,bus='usb')
        self.assertEqual(profile.kind,'ssd')
        self.assertEqual(profile.confidence,'model')
        self.assertIn('unverified',profile.evidence)
        self.assertFalse(advise(model=label,bus='usb').can_attempt_hdd_refresh)
        # SMART claiming a magnetic drive conflicts with the model; fail closed.
        self.assertEqual(identify_profile(model=label,media_type='hdd').kind,'unknown')

    def test_cli_rejects_unknown_usb_medium_before_scanning(self):
        from types import SimpleNamespace
        import contextlib, io
        from driverepair_desktop.cli import run
        from driverepair_desktop import cli
        disk=SimpleNamespace(id='linux:/dev/fake',path='/dev/fake',model='Unidentified USB',
            size_bytes=1048576,sector_size=512,serial='fake1',bus='usb',
            fingerprint='11223344556677889900')
        with (mock.patch.object(cli,'select_external_device',return_value=disk),
              mock.patch.object(cli,'list_external_devices',return_value=[disk]),
              mock.patch.object(cli,'assert_windows_external_write_gate'),
              mock.patch.object(cli,'assert_patient_idle_windows'),
              mock.patch.object(cli,'_verify_linux_patient_not_in_use'),
              mock.patch.object(cli,'try_health_snapshot',return_value={
                'status':'smart_passed_limited','reported_medium':'unknown'}),
              mock.patch.object(cli,'scan_reader') as scan,
              mock.patch.object(cli,'open_device_readwrite') as writer,
              contextlib.redirect_stderr(io.StringIO())):
            args=['care-external','--device',disk.id,'--mode','quick',
                  '--journal-backend','memory','--ack-volatile-journal',
                  '--ack-dock-power-backed','--ack-risk','--ack-destructive',
                  '--ack-no-backup','--ack-data-loss-risk','--ack-usb-bridge-risk',
                  '--ack-unvalidated-hardware','--ack-unknown-health',
                  '--confirm-identity',disk.fingerprint[:12], '--json']
            self.assertNotEqual(run(args),0)
            scan.assert_not_called()
            writer.assert_not_called()

    def test_unknown_usb_medium_no_rewrite_even_when_acknowledged(self):
        scan={'status':'completed_with_slow_regions','mode':'full',
              'device_size_bytes':8192,'read_error_chunks':0,
              'slow_regions':[{'offset':0,'length':512,'latency_ms':100}]}
        policy=plan_targeted_refresh(scan,sector=512,chunk=512,
                hardware=True,smart={'status':'smart_passed_limited',
                                     'reported_medium':'unknown'},
                allow_unknown_health=True,allow_media_warning=True)
        self.assertEqual(policy['status'],'blocked')
        self.assertEqual(policy['targets'],[])
        self.assertIn('Rotational HDD', ' '.join(policy['reasons']))

if __name__=='__main__':
    unittest.main()
