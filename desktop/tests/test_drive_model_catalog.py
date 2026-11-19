"""Bundled model provenance, exactness, and safe policy defaults."""
import unittest
from driverepair_desktop.drive_model_catalog import catalog_entries, match_catalog_models
from driverepair_desktop.media_profiles import identify_profile


class DriveModelCatalogTests(unittest.TestCase):
    def test_every_entry_has_manufacturer_and_source(self):
        rows = catalog_entries()
        self.assertGreaterEqual(len(rows), 4)
        self.assertTrue(all(row['manufacturer'] and row['source_url'].startswith('https://') for row in rows))

    def test_exact_seagate_and_nonmatching_models(self):
        self.assertEqual(identify_profile(model='ST1000LM 048-2E7172', bus='usb').kind, 'smr')
        self.assertEqual(identify_profile(model='ST1000LM0480', bus='usb').kind, 'unknown')
        self.assertFalse(match_catalog_models('ST2000LM015'))

    def test_sandisk_family_is_advisory_and_not_hdd(self):
        self.assertEqual(identify_profile(model='SanDisk SDSSDH3 500G USB Device',bus='usb').kind,'ssd')
        self.assertEqual(identify_profile(model='SDSSDH35',bus='usb').kind,'unknown')
        self.assertEqual(identify_profile(model='SDSSDH3',bus='usb',media_type='hdd').kind,'unknown')

    def test_same_bridge_not_construed_as_model(self):
        self.assertEqual(identify_profile(model='Generic USB Device',bus='usb').kind,'unknown')

if __name__ == '__main__':
    unittest.main()
