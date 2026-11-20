"""No physical media touched: regression for b29 repair routing and ISO features."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from driverepair_desktop.devices import Device
from driverepair_desktop.linux_media import linux_sysfs_snapshot
from driverepair_desktop.repair_routes import choose_repair_route
from driverepair_desktop.repair_readiness import ui_repair_readiness
from driverepair_desktop.boot_media import export_build_kit

ROOT=Path(__file__).resolve().parents[2]


class RepairViewTests(unittest.TestCase):
    def test_ssd_repair_routes_to_logical_filesystem_not_hdd_write(self):
        drive={'model':'SanDisk SDSSDH3 500G USB Device','bus':'usb',
               'sector_size':512,'serial_suffix':'***0000','identity_hint':'abc'}
        route=choose_repair_route(drive)
        self.assertEqual(route.action,'filesystem')
        self.assertIn('filesystem',route.button.lower())
        self.assertNotIn('image',route.button.lower())
        self.assertTrue(route.patient_write_possible)
        self.assertFalse(route.hdd_region_write_candidate)
        self.assertFalse(ui_repair_readiness(drive,'carequick')[0])

    def test_qt_repair_does_not_auto_redirect_to_image_rescue(self):
        src=(ROOT/'desktop/driverepair_desktop/qtgui.py').read_text(encoding='utf-8')
        start=src[src.index('        def start_job('):src.index('        def reveal_job_evidence(')]
        self.assertIn("if route.action == 'filesystem':",start)
        self.assertIn('self.start_windows_filesystem_repair()',start)
        self.assertNotIn('recovery_here = True',start)
        self.assertNotIn("self.select_goal('rescue')",start)
        self.assertIn("'repair-windows-filesystem'",src)
        self.assertIn('Restore data',src)


class LinuxEvidenceTests(unittest.TestCase):
    def make(self,td,*,disk='sdb',rotation='1',sectors='4096',size=2097152):
        root=Path(td)/'block'
        p=root/disk
        (p/'queue').mkdir(parents=True)
        (p/'device').mkdir()
        (p/'size').write_text(sectors)
        (p/'queue'/'logical_block_size').write_text('512')
        (p/'queue'/'rotational').write_text(rotation)
        (p/'queue'/'discard_max_bytes').write_text('0')
        (p/'device'/'model').write_text('USB Bridge')
        drive=Device('linux:/dev/'+disk,'/dev/'+disk,'ST1000LM048',size,512,'usb','serial')
        return root,drive

    def test_rotational_only_hint_not_write_authorization(self):
        with tempfile.TemporaryDirectory() as td:
            root,dev=self.make(td)
            snap=linux_sysfs_snapshot(dev,root=root)
            self.assertEqual(snap['reported_medium'],'hdd')
            self.assertEqual(snap['status'],'unknown')
            self.assertFalse(snap['native_hdd_corrob'])
            self.assertIn('bridge',snap['notes'])
            ok,_=ui_repair_readiness(dev.public(),'carequick',snap)
            self.assertFalse(ok)

    def test_reject_partition_and_geometry_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root,dev=self.make(td)
            bad=Device('linux:/dev/sdb1','/dev/sdb1',dev.model,dev.size_bytes,512,'usb','serial')
            self.assertIsNone(linux_sysfs_snapshot(bad,root=root))
            bad=Device(dev.id,dev.path,dev.model,dev.size_bytes+512,512,'usb','serial')
            self.assertIsNone(linux_sysfs_snapshot(bad,root=root))

    def test_no_smart_fallback_can_only_report_unknown_health(self):
        from driverepair_desktop import health
        with tempfile.TemporaryDirectory() as td:
            root,dev=self.make(td,rotation='0')
            with (mock.patch.object(health,'health_snapshot',side_effect=RuntimeError('SAT unavailable')),
                  mock.patch('driverepair_desktop.linux_media.linux_sysfs_snapshot',
                             return_value=linux_sysfs_snapshot(dev,root=root))):
                snap=health.try_health_snapshot(dev)
            self.assertEqual(snap['reported_medium'],'ssd')
            self.assertEqual(snap['smart_unavailable_reason'],'SAT unavailable')
            self.assertFalse(snap['native_hdd_corrob'])


class LiveBuildTests(unittest.TestCase):
    def test_live_scripts_include_ram_cpu_boot_diagnostics(self):
        for rel in ('scripts/build_live_iso.sh','desktop/driverepair_desktop/boot_resources/build_live_iso.sh'):
            text=(ROOT/rel).read_text()
            for piece in ('--memtest memtest86+', 'stress-ng', 'stressapptest',
                          'driverepair-hardware-diagnostics', 'Terminal=true'):
                self.assertIn(piece,text)
        s=(ROOT/'scripts/driverepair-hardware-diagnostics.sh').read_text()
        self.assertNotIn('--hdd',s)
        self.assertIn('--timeout 120s',s)

    def test_standalone_kit_includes_hardware_diagnostic_script(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'build-kit.zip'
            export_build_kit(None,path)
            with zipfile.ZipFile(path) as z:
                members=z.namelist()
                self.assertIn('driverepair/scripts/driverepair-hardware-diagnostics.sh',members)
                build=z.read('driverepair/scripts/build_live_iso.sh').decode()
                self.assertIn('--memtest memtest86+',build)

if __name__=='__main__':
    unittest.main()
