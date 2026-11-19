"""Regression: compatible Windows USB SAT bridges can identify HDDs without SMART.

All tests are synthetic: no hardware IO is performed on the test runner.
"""
import json
import struct
import subprocess
import unittest
from argparse import Namespace
from unittest import mock

from driverepair_desktop.ata_identity import (
    SOURCE, _SCSI_PASS_THROUGH, interpret_sat_evidence, parse_ata_identify,
    sat_identify_cdb, windows_ata_snapshot,
)
from driverepair_desktop.devices import Device
from driverepair_desktop import ata_identity, release_policy
from driverepair_desktop.repair_strategy import advise
from driverepair_desktop.repair_readiness import ui_repair_readiness


def device(model='ST1000LM048-2E7172', serial='SN0001'):
    return Device('windows:PhysicalDrive4', r'\\.\PhysicalDrive4',
                  model, 1000204886016, 512, 'usb', serial)


def sample(*, model='ST1000LM048-2E7172', serial='SN0001', rpm=5400,
           size=1000204886016):
    words = [0] * 256
    words[0] = 0x40
    def string(start, count, text):
        raw = text.ljust(2 * count).encode('ascii')
        for i in range(count):
            words[start + i] = (raw[2*i] << 8) | raw[2*i+1]
    string(10, 10, serial)
    string(27, 20, model)
    sectors = size // 512
    for k in range(4):
        words[100 + k] = (sectors >> (16*k)) & 0xffff
    words[217] = rpm
    return struct.pack('<256H', *words)


class SATIdentificationTests(unittest.TestCase):
    def test_only_identify_read_command_is_encoded(self):
        command = sat_identify_cdb()
        self.assertEqual(len(command), 16)
        self.assertEqual(command, bytes.fromhex('85080e0000000100000000000000ec00'))
        self.assertGreaterEqual(__import__('ctypes').sizeof(_SCSI_PASS_THROUGH), 44)

    def test_parse_hdd_and_ssd_and_unknown_rotation(self):
        result = parse_ata_identify(sample())
        self.assertEqual(result['reported_medium'], 'hdd')
        self.assertEqual(result['size_bytes'], 1000204886016)
        self.assertEqual(result['rotation_rate'], 5400)
        self.assertEqual(result['serial_suffix'], '***0001')
        self.assertEqual(parse_ata_identify(sample(rpm=1))['reported_medium'], 'ssd')
        self.assertEqual(parse_ata_identify(sample(rpm=0))['reported_medium'], 'unknown')

    def test_reject_packet_empty_and_incomplete_identity(self):
        for invalid in (b'', bytes(512), sample()[:480]):
            with self.assertRaises(ValueError):
                parse_ata_identify(invalid)
        packet = bytearray(sample())
        packet[1] = 0x80
        with self.assertRaises(ValueError):
            parse_ata_identify(bytes(packet))

    def test_corrob_requires_all_identity_factors(self):
        base = parse_ata_identify(sample())
        report = interpret_sat_evidence(device(), base)
        self.assertEqual(report['source'], SOURCE)
        self.assertTrue(report['native_hdd_corrob'])
        self.assertEqual(report['status'], 'unknown')
        self.assertTrue(advise(model=device().model, bus='usb', snapshot=report).can_attempt_hdd_refresh)
        self.assertTrue(ui_repair_readiness(device().public(), 'carequick', report)[0])
        for change in ({'size_bytes':1000204886016-512},
                       {'logical_sector_bytes':4096},
                       {'reported_medium':'ssd'}, {'serial_suffix':'***9999'},
                       {'model':'Fake SSD Controller'}):
            with self.subTest(change=change):
                self.assertIsNone(interpret_sat_evidence(device(), {**base, **change}))
        self.assertIsNone(interpret_sat_evidence(device(model='SanDisk SDSSDH3 500G'),
                                                   {**base, 'model':'SanDisk SDSSDH3 500G'}))

    def test_bounded_read_only_child_and_failure(self):
        result = {**parse_ata_identify(sample()), 'number':4}
        mock_runner = mock.Mock(return_value=subprocess.CompletedProcess([],0,stdout=json.dumps(result).encode()))
        with mock.patch.object(ata_identity.sys,'platform','win32'):
            report = windows_ata_snapshot(device(), runner=mock_runner)
            self.assertEqual(report['source'], SOURCE)
            self.assertEqual(mock_runner.call_args.kwargs['timeout'], 8)
            self.assertEqual(mock_runner.call_args.args[0][-3:], ['inspect-windows-ata','--number','4'])
            mock_runner.side_effect = subprocess.TimeoutExpired('identify',8)
            self.assertIsNone(windows_ata_snapshot(device(),runner=mock_runner))

    def test_smart_failure_uses_sat_after_native_inconclusive(self):
        from driverepair_desktop import health
        qualified = interpret_sat_evidence(device(), parse_ata_identify(sample()))
        inconclusive = {'source':'windows_native_unverified', 'status':'unknown',
                        'reported_medium':'unknown', 'native_hdd_corrob':False}
        with (mock.patch.object(health, 'health_snapshot', side_effect=RuntimeError('SMART unavailable')),
              mock.patch('driverepair_desktop.native_media.windows_native_snapshot',
                         return_value=inconclusive),
              mock.patch('driverepair_desktop.ata_identity.windows_ata_snapshot',
                         return_value=qualified),
              mock.patch.object(health,'windows_storage_health',return_value=None)):
            result = health.try_health_snapshot(device())
        self.assertEqual(result['source'], SOURCE)
        self.assertEqual(result['status'], 'unknown')
        self.assertIn('SMART unavailable', result['smart_unavailable_reason'])

    def test_native_reports_ssd_conflict_is_not_overridden(self):
        from driverepair_desktop import health
        qualified = interpret_sat_evidence(device(), parse_ata_identify(sample()))
        contradictory = {'source':'windows_native_unverified','status':'unknown',
                         'reported_medium':'ssd','native_hdd_corrob':False}
        with (mock.patch.object(health, 'health_snapshot', side_effect=RuntimeError('SMART unavailable')),
              mock.patch('driverepair_desktop.native_media.windows_native_snapshot',
                         return_value=contradictory),
              mock.patch('driverepair_desktop.ata_identity.windows_ata_snapshot',
                         return_value=qualified) as probe,
              mock.patch.object(health, 'windows_storage_health',return_value=None)):
            response = health.try_health_snapshot(device())
        self.assertEqual(response['reported_medium'],'ssd')
        self.assertFalse(response['native_hdd_corrob'])
        probe.assert_not_called()

    def test_smart_media_failure_cannot_be_replaced_with_ata_hint(self):
        from driverepair_desktop import health
        failed = {'source':'smartctl_auto', 'reported_medium':'unknown',
                  'status':'failure_reported', 'ata_selected_raw_attributes':[]}
        with mock.patch.object(health,'health_snapshot',return_value=failed):
            self.assertEqual(health.try_health_snapshot(device()), failed)

    def test_guarded_engine_still_needs_explicit_risk_and_journal(self):
        report = interpret_sat_evidence(device(), parse_ata_identify(sample()))
        args = Namespace(command='care-external', journal_backend='disk',
                         journal='/healthy/new-journal', rewrite_neighbors=False,
                         recording='auto', ack_unknown_health=False, max_regions=16,
                         auto_lock_volumes=True, ack_media_warning=False)
        with mock.patch.object(release_policy,'REPAIR_BETA_GUARDED',True):
            with self.assertRaisesRegex(PermissionError, 'ack-unknown-health'):
                release_policy.check_guarded_repair_preflight(args,report,device())
            args.ack_unknown_health = True
            self.assertTrue(release_policy.check_guarded_repair_preflight(args,report,device())['can_attempt_hdd_refresh'])
            args.journal = None
            with self.assertRaises(PermissionError):
                release_policy.check_guarded_repair_preflight(args,report,device())

if __name__=='__main__':
    unittest.main()
