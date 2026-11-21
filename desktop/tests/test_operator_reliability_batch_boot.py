"""Offline guarantees for condition scoring, batch preflight and ISO kit."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from driverepair_desktop.reliability_score import assess, compare_assessments
from driverepair_desktop.unattended import plan_rescue_batch, store_manifest, append_batch_event
from driverepair_desktop.boot_media import export_build_kit
from driverepair_desktop.progress_events import ProgressEmitter
from driverepair_desktop.surface_map import SurfaceCoverage


class ConditionTests(unittest.TestCase):
    def test_unknown_and_coarse_windows_health_never_get_numeric_score(self):
        self.assertIsNone(assess(None)['score'])
        self.assertIsNone(assess({'source': 'windows_storage_healthstatus', 'status': 'windows_health_limited'})['score'])
        self.assertIsNone(assess({'status': 'smart_passed_limited'})['score'])

    def test_raw_ata_media_warnings_decrease_condition_index(self):
        # Penalties require explicit model thresholds; uncalibrated positives stay unscored.
        specs={'ata_raw_thresholds': {5: 0, 197: 0, 198: 0}}
        baseline={'status':'smart_passed_limited', 'smart_status_passed': True,
                  'ata_selected_raw_attributes':[
                     {'id':5,'raw_value':0}, {'id':9,'raw_value':10000},
                     {'id':197,'raw_value':0}, {'id':198,'raw_value':0}]}
        worsening={**baseline, 'ata_selected_raw_attributes': [
            {'id':5,'raw_value':4}, {'id':9,'raw_value':10001},
            {'id':197,'raw_value':2}, {'id':198,'raw_value':1}]}
        good=assess(baseline, manufacturer_specs=specs)
        bad=assess(worsening, manufacturer_specs=specs)
        self.assertEqual(good['power_on_hours'],10000)
        self.assertLess(bad['score'],good['score'])
        self.assertIsNone(assess(worsening)['score'])  # uncalibrated positives → no numeric badge
        self.assertLess(compare_assessments(baseline, worsening, manufacturer_specs=specs)['delta'], 0)

    def test_nvme_critical_warn_and_exhausted_spare(self):
        snap={'status':'failure_reported','nvme':{'critical_warning':1,
              'media_errors':10,'available_spare':5, 'available_spare_threshold':10,
              'percentage_used':110,'power_on_hours':15000}}
        view=assess(snap)
        self.assertLess(view['score'],35)
        self.assertIn('CRITICAL',view['band'])

    def test_only_explicit_manufacturer_rating_applies(self):
        snap={'smart_status_passed':True,'ata_selected_raw_attributes':[
             {'id':5,'raw_value':0},{'id':197,'raw_value':0},{'id':9,'raw_value':30000}]}
        self.assertEqual(assess(snap)['score'],100)
        self.assertEqual(assess(snap,manufacturer_specs={'rated_power_on_hours':20000})['score'],90)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.devices=[{'id':f'usb:{i}', 'identity_hint':f'0123456789{i:02d}',
                       'size_bytes':4096,'model':f'Sample Disk {i}'} for i in (1,2)]

    def test_unique_new_destinations_and_durable_manifest(self):
        planned=plan_rescue_batch(self.devices,self.temp.name,free_bytes=2*1024**3)
        self.assertEqual(len({p['output'] for p in planned}),2)
        path=Path(self.temp.name)/'manifest.json'
        store_manifest(path,planned)
        self.assertTrue(path.is_file())
        append_batch_event(path,dict(planned[0],status='FAILED',exit_code=2))
        self.assertIn('FAILED', Path(str(path)+'.events.jsonl').read_text())
        with self.assertRaises(FileExistsError):
            store_manifest(path,planned)

    def test_reject_existing_output_duplicate_identity_and_low_space(self):
        with self.assertRaises(ValueError):
            plan_rescue_batch(self.devices*2,self.temp.name,free_bytes=2*1024**3)
        with self.assertRaises(ValueError):
            plan_rescue_batch(self.devices,self.temp.name,free_bytes=512)
        target=plan_rescue_batch(self.devices,self.temp.name,free_bytes=2*1024**3)[0]['output']
        Path(target).touch()
        with self.assertRaises(FileExistsError):
            plan_rescue_batch(self.devices,self.temp.name,free_bytes=2*1024**3)


class EvidenceTests(unittest.TestCase):
    def test_throttling_does_not_discard_completed_read_spans(self):
        buffer=io.StringIO()
        emitter=ProgressEmitter(enabled=True,stream=buffer,min_interval_s=60)
        with patch('driverepair_desktop.progress_events.time.monotonic',side_effect=[100,101,102,103]):
            for i in range(4):
                emitter.emit({'phase':'SCANNING','offset':i*256,'read_length':256,
                              'size':1024,'failed':i == 2},force=i==3)
        out=[json.loads(line) for line in buffer.getvalue().splitlines()]
        spans=[span for event in out for span in event.get('observed_read_spans',[])]
        cov=SurfaceCoverage(1024,cells=4)
        for off,length,failed,slow in spans:
            cov.observe(off,length,failed=failed,slow=slow)
        self.assertEqual(cov.checked_bytes,768)
        self.assertEqual(sum(c.read_errors for c in cov.cells),1)

    def test_sequential_reads_merge_and_cover_full_device(self):
        buffer=io.StringIO()
        emitter=ProgressEmitter(enabled=True,stream=buffer,min_interval_s=10000)
        with patch('driverepair_desktop.progress_events.time.monotonic',return_value=10):
            for i in range(500):
                emitter.emit({'phase':'SCANNING','offset':i*2048,'read_length':2048,
                              'size':500*2048,'failed':False},force=(i==499))
        events=[json.loads(line) for line in buffer.getvalue().splitlines()]
        spans=[span for event in events for span in event.get('observed_read_spans',[])]
        self.assertEqual(spans,[[0,1024000,False,False]])


class BootKitTests(unittest.TestCase):
    def test_build_kit_has_recipe_and_never_writes_raw_media(self):
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'builder.zip'
            result=export_build_kit(root,target)
            self.assertEqual(result['status'],'UNVERIFIED_BUILD_KIT_CREATED')
            with zipfile.ZipFile(target) as archive:
                paths=set(archive.namelist())
            self.assertIn('driverepair/scripts/build_live_iso.sh',paths)
            self.assertIn('driverepair/desktop/driverepair_desktop/qtgui.py',paths)
            self.assertIn('driverepair/BOOT_KIT_INSTRUCTIONS.txt',paths)
            with self.assertRaises(FileExistsError):
                export_build_kit(root,target)

    def test_standalone_resource_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'portable-kit.zip'
            result=export_build_kit(None,output)
            self.assertEqual(result['status'],'UNVERIFIED_BUILD_KIT_CREATED')
            with zipfile.ZipFile(output) as archive:
                self.assertIn('driverepair/scripts/build_live_iso.sh',archive.namelist())
                self.assertIn('driverepair/desktop/driverepair_desktop/qtgui.py',archive.namelist())


if __name__=='__main__':
    unittest.main()
