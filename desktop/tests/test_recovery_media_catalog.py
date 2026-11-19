"""Local image selection and safe UI preflight (no device writes)."""
from pathlib import Path
import tempfile
import unittest

from driverepair_desktop.recovery_media_catalog import find_local_recovery_iso
from driverepair_desktop.repair_readiness import ui_repair_readiness


def minimal_hybrid(path: Path, *, size=131072):
    data=bytearray(size)
    data[510:512]=b'\x55\xaa'
    data[16*2048+1:16*2048+6]=b'CD001'
    path.write_bytes(data)


class ImageDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_no_iso_does_not_invent_or_download_one(self):
        self.assertIsNone(find_local_recovery_iso(search_roots=[self.root]))

    def test_preselects_real_driverepair_hybrid(self):
        minimal_hybrid(self.root/'DriveRepair-Live-amd64.iso')
        found=find_local_recovery_iso(search_roots=[self.root])
        self.assertIsNotNone(found)
        self.assertEqual(Path(found['path']).name,'DriveRepair-Live-amd64.iso')
        self.assertEqual(found['selection'],'local_driverepair_image')

    def test_bad_image_skipped_and_generic_iso_not_auto_selected(self):
        (self.root/'DriveRepair-Live-broken.iso').write_bytes(b'not an ISO')
        minimal_hybrid(self.root/'Ubuntu.iso')
        self.assertIsNone(find_local_recovery_iso(search_roots=[self.root]))

    def test_preferred_image_used_after_restart(self):
        custom=self.root/'custom.iso'
        minimal_hybrid(custom)
        self.assertEqual(find_local_recovery_iso(preferred=str(custom),search_roots=[])['selection'],
                         'previously_selected')

    def test_bad_preferred_falls_back_to_local_build(self):
        good=self.root/'DriveRepair-Live-amd64.iso'
        minimal_hybrid(good)
        selected=find_local_recovery_iso(preferred=str(self.root/'missing.iso'),search_roots=[self.root])
        self.assertEqual(selected['path'],str(good.resolve()))

    def test_symlink_cannot_be_auto_selected(self):
        good=self.root/'DriveRepair-Live-good.iso'
        minimal_hybrid(good)
        symlink=self.root/'DriveRepair-Live-new.iso'
        try: symlink.symlink_to(good)
        except (OSError,NotImplementedError): self.skipTest('symlink unavailable')
        found=find_local_recovery_iso(preferred=str(symlink),search_roots=[])
        self.assertIsNone(found)


class RepairReadinessTests(unittest.TestCase):
    def test_missing_serial_fails_before_any_io(self):
        self.assertFalse(ui_repair_readiness({'serial_suffix':'unavailable','bus':'usb'},'carequick')[0])
        self.assertFalse(ui_repair_readiness({'serial_suffix':'','bus':'usb'},'carefull')[0])
        self.assertTrue(ui_repair_readiness({'serial_suffix':'unavailable','bus':'usb'},'rescue')[0])

    def test_serial_is_necessary_not_sufficient(self):
        device={'serial_suffix':'***abcd','bus':'usb','model':'ST1000LM048','sector_size':512}
        self.assertFalse(ui_repair_readiness(device,'carequick')[0])
        self.assertFalse(ui_repair_readiness({'serial_suffix':'***abcd','bus':'sata'},'carequick')[0])
        snap={'status':'smart_passed_limited','reported_medium':'hdd',
              'rotation_rate_rpm':5400,'ata_selected_raw_attributes':[]}
        ready,note=ui_repair_readiness(device,'carequick',snapshot=snap)
        self.assertTrue(ready,note)
        self.assertIn('engine must still',note)
        for medium in ('ssd','unknown','flash drive'):
            self.assertFalse(ui_repair_readiness(device,'carequick',snapshot={
                'status':'smart_passed_limited','reported_medium':medium,
                'ata_selected_raw_attributes':[]})[0])
        self.assertTrue(ui_repair_readiness(device,'rescue')[0])


if __name__=='__main__': unittest.main()
