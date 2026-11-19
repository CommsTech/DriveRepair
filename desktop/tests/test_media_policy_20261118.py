"""Evidence-driven medium classification and bounded read-only investigation."""
import unittest
from driverepair_desktop.media_profiles import identify_profile
from driverepair_desktop.repair_strategy import advise
from driverepair_desktop.guided_repair import tuned_scan, investigate_failed_ranges

class DummyReader:
    def __init__(self):
        self.calls = []
    def read_at(self, offset, length):
        self.calls.append((offset, length))
        return b'Z' * length

class TestMediaPolicy(unittest.TestCase):
    def test_nvr_label_never_implies_recording_type(self):
        p = identify_profile(model='Seagate SkyHawk 4TB', bus='usb', media_type='hdd')
        self.assertEqual(p.kind, 'hdd_unknown_recording')
        self.assertEqual(p.workload, 'surveillance')
        self.assertFalse(p.neighbor_rewrite)

    def test_exact_smr_model_over_usb_with_rotational_evidence(self):
        p = identify_profile(model='ST1000LM048-2E7172', bus='usb', media_type='hdd')
        self.assertEqual(p.kind, 'smr')
        self.assertIn('sequential',p.recovery_method.lower())

    def test_conflicting_media_evidence_fails_closed(self):
        for kwargs in (
            {'model':'ST1000LM048', 'recording':'cmr', 'media_type':'hdd'},
            {'model':'ST1000LM048', 'media_type':'ssd', 'bus':'usb'},
            {'media_type':'hdd', 'protocol':'nvme'},
        ):
            p = identify_profile(**kwargs)
            self.assertEqual(p.kind, 'unknown', kwargs)
            self.assertEqual(p.confidence, 'conflict')

    def test_removable_flash_only_when_reported(self):
        self.assertEqual(identify_profile(bus='usb').kind, 'unknown')
        p=identify_profile(bus='usb', media_type='flash drive')
        self.assertEqual(p.kind,'flash')
        snap={'status':'smart_passed_limited','reported_medium':'flash drive','nvme':{},
              'ata_selected_raw_attributes':[]}
        advice=advise(bus='usb', snapshot=snap)
        self.assertFalse(advice.can_attempt_hdd_refresh)
        self.assertIn(advice.path, ('ssd_diagnostics','rescue_replace'))

    def test_nvme_detected_through_usb_from_health_protocol(self):
        snap={'status':'smart_passed_limited','reported_medium':'ssd','device_protocol':'nvme',
              'nvme':{'percentage_used':12},'ata_selected_raw_attributes':[]}
        advice=advise(bus='usb', snapshot=snap)
        self.assertEqual(advice.profile,'nvme')
        self.assertFalse(advice.can_attempt_hdd_refresh)

    def test_magnetic_model_alone_does_not_authorize_write(self):
        snap={'status':'smart_passed_limited','reported_medium':'unknown','nvme':{},
              'ata_selected_raw_attributes':[]}
        advice=advise(model='ST1000LM048',bus='usb',snapshot=snap)
        self.assertFalse(advice.can_attempt_hdd_refresh)

    def test_tuned_scan_uses_protocol_and_media(self):
        plan=tuned_scan(size=1024*1024*1024,sector=512,mode='full',bus='usb',
                        media_type='ssd',protocol='nvme')
        self.assertEqual(plan['profile'],'nvme')
        self.assertIn('no raw NAND',plan['recovery_method'])

    def test_retry_probe_caps_read_size_before_first_attempt(self):
        reader=DummyReader()
        result=investigate_failed_ranges(reader,[{'offset':0,'length':1024*1024}],
                                          sector=512,max_reads=4, max_regions=1)
        self.assertLessEqual(max(length for _,length in reader.calls),64*1024)
        self.assertLessEqual(result['read_calls'],4)
        self.assertTrue(result['budget_exhausted'])

    def test_retry_budget_rejects_unaligned_max(self):
        with self.assertRaises(ValueError):
            investigate_failed_ranges(DummyReader(),[],sector=4096,max_probe_bytes=1000)

if __name__ == '__main__':
    unittest.main()

class TestFlashWriteInhibition(unittest.TestCase):
    def test_even_engineering_planner_blocks_flash_rewrites(self):
        from driverepair_desktop.guided_repair import plan_targeted_refresh
        scan={'status':'completed_with_slow_regions','mode':'triage',
              'device_size_bytes':8192,'slow_regions':[{'offset':0,'latency_ms':200}],
              'read_error_chunks':0}
        for medium in ('ssd','nvme','flash drive'):
            snapshot={'status':'smart_passed_limited','reported_medium':medium,
                      'nvme':{},'ata_selected_raw_attributes':[]}
            plan=plan_targeted_refresh(scan,sector=512,chunk=1024,
                                       smart=snapshot,hardware=True,
                                       allow_unknown_health=True,allow_media_warning=True)
            self.assertEqual(plan['status'],'blocked')
            self.assertEqual(plan['targets'],[])

class TestLazyReadBounds(unittest.TestCase):
    def test_one_terabyte_failure_stays_memory_bounded(self):
        reader=DummyReader()
        report=investigate_failed_ranges(reader,[{'offset':0,'length':2**40}],
                                          sector=512,max_reads=2)
        self.assertEqual(len(reader.calls),2)
        self.assertTrue(all(length<=64*1024 for _,length in reader.calls))
        self.assertTrue(report['budget_exhausted'])
        self.assertTrue(report['unresolved_regions'])
