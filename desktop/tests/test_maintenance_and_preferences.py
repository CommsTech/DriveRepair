import errno
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from driverepair_desktop.devices import Device
from driverepair_desktop.preferences import DEFAULTS, load_preferences, save_preferences
from driverepair_desktop.maintenance import (firmware_inventory, volume_optimization_plan,
                                              execute_optimization, windows_volume_facts)
from driverepair_desktop.diagnostics import probe_range

DISK = Device('windows:PhysicalDrive2', r'\\.\PhysicalDrive2', 'ST1000LM048',
              1000204886016, 512, 'usb', 'synthetic999')


class PreferencesTests(unittest.TestCase):
    def test_preferences_round_trip_only_allowed_values(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'prefs.json'
            save_preferences({'schema': 1, 'repair_storage': 'memory',
                              'repair_policy': 'preserve', 'dashboard': True,
                              'risk_accepted': True, 'last_device': 'patient-serial'}, p)
            data = load_preferences(p)
            self.assertEqual(data['repair_storage'], 'memory')
            self.assertEqual(data['repair_policy'], 'preserve')
            self.assertTrue(data['dashboard'])
            self.assertNotIn('risk_accepted', p.read_text())
            self.assertNotIn('patient-serial', p.read_text())

    def test_invalid_preferences_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'prefs.json'
            p.write_text('{bad json')
            self.assertEqual(load_preferences(p), DEFAULTS)
            p.write_text(json.dumps({'schema': 1, 'repair_storage': 'shred',
                                     'repair_policy': 'erase', 'dashboard': 'yes'}))
            self.assertEqual(load_preferences(p), DEFAULTS)


class FirmwareTests(unittest.TestCase):
    def test_unknown_revision_never_called_up_to_date(self):
        with mock.patch('driverepair_desktop.maintenance.sys.platform', 'linux'):
            r = firmware_inventory(DISK, run=lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
        self.assertIsNone(r['installed_revision'])
        self.assertEqual(r['update_available'], 'NOT_CHECKED')
        self.assertFalse(r['firmware_update_performed'])
        self.assertIn('seagate.com', r['manufacturer_lookup'])

    def test_firmware_revision_does_not_imply_update_available(self):
        proc = mock.Mock(returncode=0, stdout=json.dumps({'Revision': 'SDM1'}).encode())
        with mock.patch('driverepair_desktop.maintenance.sys.platform', 'win32'):
            r = firmware_inventory(DISK, run=lambda *a, **kw: proc)
        self.assertEqual(r['installed_revision'], 'SDM1')
        self.assertEqual(r['update_available'], 'NOT_CHECKED')


class VolumeOptimizerTests(unittest.TestCase):
    def facts(self, **updates):
        values = dict(DiskNumber=2, DriveLetter='E', IsBoot=False, IsSystem=False,
                      FileSystem='NTFS', MediaType='HDD', HealthStatus='Healthy')
        values.update(updates)
        return values

    def test_hdd_ssd_unknown_policies(self):
        a = volume_optimization_plan(disk=DISK, letter='e', facts=self.facts(),
                                     smart_state='smart_passed_limited')
        self.assertEqual(a['recommendation'], 'defrag')
        self.assertTrue(a['eligible_to_execute'])
        a = volume_optimization_plan(disk=DISK, letter='E', facts=self.facts(MediaType='SSD'),
                                     smart_state='smart_passed_limited')
        self.assertEqual(a['recommendation'], 'retrim')
        a = volume_optimization_plan(disk=DISK, letter='E', facts=self.facts(MediaType='Unspecified'),
                                     smart_state='smart_passed_limited')
        self.assertEqual(a['recommendation'], 'analyze')
        self.assertFalse(a['eligible_to_execute'])

    def test_health_unknown_and_warnings_block_writes(self):
        for state in ('unknown', 'windows_health_limited', 'media_warning'):
            plan = volume_optimization_plan(disk=DISK, letter='E', facts=self.facts(),
                                            smart_state=state)
            self.assertFalse(plan['eligible_to_execute'])
            with self.assertRaises(ValueError):
                execute_optimization(plan)

    def test_mismatched_or_system_volume_is_rejected(self):
        for facts in (self.facts(DiskNumber=1), self.facts(IsBoot=True),
                      self.facts(DriveLetter='F'), self.facts(IsSystem=True)):
            with self.assertRaises(ValueError):
                volume_optimization_plan(disk=DISK, letter='E', facts=facts)

    def test_windows_facts_query_is_escaped_and_read_only(self):
        proc = mock.Mock(returncode=0, stdout=json.dumps(self.facts()).encode())
        with mock.patch('driverepair_desktop.maintenance.sys.platform', 'win32'):
            data = windows_volume_facts(DISK, 'E', run=lambda *a, **kw: proc)
        self.assertEqual(data['DriveLetter'], 'E')
        with mock.patch('driverepair_desktop.maintenance.sys.platform', 'win32'):
            with self.assertRaises(ValueError):
                windows_volume_facts(DISK, 'E;rm C:', run=lambda *a, **kw: proc)


class RegionProbeTests(unittest.TestCase):
    def test_split_failed_large_read_without_writing(self):
        class Reader:
            def __init__(self):
                self.calls = []
            def read_at(self, offset, length):
                self.calls.append((offset, length))
                if length == 4096:
                    raise OSError(errno.EINVAL, 'invalid request')
                return b'A' * length
        reader = Reader()
        result = probe_range(reader, offset=0, length=4096, sector=512, size=8192)
        self.assertGreaterEqual(result['reads_attempted'], 3)
        self.assertEqual(result['status'], 'investigation_required')
        self.assertEqual(reader.calls[0], (0, 4096))

    def test_winerror_1117_does_not_stress_device(self):
        class Reader:
            calls = 0
            def read_at(self, offset, length):
                self.calls += 1
                exc = OSError(errno.EIO, 'device I/O error')
                exc.winerror = 1117
                raise exc
        r = Reader()
        status = probe_range(r, offset=0, length=4096, sector=512, size=8192)
        self.assertEqual(r.calls, 1)
        self.assertEqual(status['unresolved_read_requests'], 1)

    def test_reject_non_aligned_or_unbounded(self):
        for args in ({'offset': 1, 'length': 4096},
                     {'offset': 0, 'length': 16 * 1024 * 1024},
                     {'offset': 8192, 'length': 4096}):
            with self.assertRaises(ValueError):
                probe_range(None, sector=512, size=8192, **args)

if __name__ == '__main__':
    unittest.main()
