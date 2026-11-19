"""Windows-independent synthetic assertions for SMART-free HDD identification.

Never opens a physical disk or grants real write access.
"""
import json
import struct
import subprocess
import unittest
from unittest import mock

from driverepair_desktop.devices import Device
from driverepair_desktop.native_media import (
    NATIVE_SOURCE, interpret_native_evidence, windows_native_snapshot,
)
from driverepair_desktop.repair_readiness import ui_repair_readiness
from driverepair_desktop.repair_strategy import advise
from driverepair_desktop.release_policy import check_guarded_repair_preflight
from driverepair_desktop.windows_native import decode_boolean_property
from driverepair_desktop import native_media, release_policy
from argparse import Namespace


def drive(model='ST1000LM048-2E7172', serial='disk-0001'):
    return Device('windows:PhysicalDrive4', r'\\.\PhysicalDrive4',
                  model, 1000204886016, 512, 'usb', serial)


def native(**overrides):
    info = dict(model='ST1000LM048-2E7172', bus='USB',
                serial_suffix='***0001', size_bytes=1000204886016,
                incurs_seek_penalty=True, trim_enabled=False)
    info.update(overrides)
    return info


class NativeHddEvidenceTests(unittest.TestCase):
    def test_strict_windows_descriptor_flag(self):
        for value in (0, 1):
            data=struct.pack('<II', 12, 12)+bytes([value, 0, 0, 0])
            self.assertIs(decode_boolean_property(data, property_name='seek'), bool(value))
        for bad in (b'', b'12345678', struct.pack('<II',12,120)+b'\1',
                    struct.pack('<II',12,12)+b'\2\0\0\0'):
            with self.assertRaises(ValueError):
                decode_boolean_property(bad, property_name='trim')

    def test_all_evidence_required_for_smr_hdd(self):
        result=interpret_native_evidence(drive(),native())
        self.assertTrue(result['native_hdd_corrob'])
        self.assertEqual(result['reported_medium'],'hdd')
        self.assertEqual(result['source'],NATIVE_SOURCE)
        self.assertEqual(result['status'],'unknown')
        self.assertIsNone(result['smart_status_passed'])
        advice=advise(model=drive().model,bus='usb',snapshot=result)
        self.assertTrue(advice.can_attempt_hdd_refresh)
        self.assertIn('explicit consent',advice.label)

    def test_bad_identity_and_driver_claims_do_not_authorize(self):
        cases=[{'size_bytes':1000204886016-512},
               {'serial_suffix':'***9999'},
               {'serial_suffix':None},
               {'model':'Generic USB-SSD Controller'},
               {'incurs_seek_penalty':False},
               {'incurs_seek_penalty':None},
               {'trim_enabled':True},
               {'trim_enabled':None},
               {'bus':'SATA'}]
        for override in cases:
            with self.subTest(override=override):
                report=interpret_native_evidence(drive(),native(**override))
                self.assertFalse(report['native_hdd_corrob'])
                self.assertFalse(advise(model=drive().model,bus='usb',snapshot=report).can_attempt_hdd_refresh)

    def test_generic_hdd_model_can_be_identified_without_assuming_cmr(self):
        d=drive(model='ST1000DM010')
        result=interpret_native_evidence(d,native(model='ST1000DM010'))
        self.assertTrue(result['native_hdd_corrob'])
        self.assertEqual(result['reported_medium'],'hdd')
        # Only media identity is established. No assumed CMR/SMR or good health.
        self.assertEqual(result['status'],'unknown')
        self.assertTrue(advise(model=d.model,bus=d.bus,snapshot=result).can_attempt_hdd_refresh)

    def test_known_ssd_is_not_hdd_even_if_driver_misreports(self):
        report=interpret_native_evidence(drive(model='SanDisk SDSSDH3 500G'),native(model='SanDisk SDSSDH3 500G'))
        self.assertFalse(report['native_hdd_corrob'])
        self.assertFalse(advise(model='SanDisk SDSSDH3 500G',bus='usb',snapshot=report).can_attempt_hdd_refresh)

    def test_known_model_cannot_substitute_for_native_confirmation(self):
        report=interpret_native_evidence(drive(),native(trim_enabled=None))
        self.assertEqual(report['reported_medium'],'unknown')

    def test_incomplete_smart_does_not_hide_actual_warning(self):
        from driverepair_desktop.health import supplement_inconclusive_smart
        inconclusive={'status':'smart_passed_limited','reported_medium':'unknown',
                      'ata_selected_raw_attributes':[], 'source':'smartctl_auto'}
        with mock.patch('driverepair_desktop.native_media.windows_native_snapshot',
                        return_value=interpret_native_evidence(drive(),native())):
            improved=supplement_inconclusive_smart(drive(),inconclusive)
            self.assertEqual(improved['source'],NATIVE_SOURCE)
            self.assertEqual(improved['status'],'unknown')
            warned={**inconclusive,'ata_selected_raw_attributes':[{'id':197,'raw_value':3}]}
            self.assertIs(supplement_inconclusive_smart(drive(),warned),warned)

    def test_native_probe_command_is_timeout_bounded(self):
        device=drive()
        commands=[]
        def runner(args, **kwargs):
            commands.append((args,kwargs))
            return subprocess.CompletedProcess(args,0,stdout=json.dumps(native()).encode())
        with mock.patch.object(native_media.sys,'platform','win32'):
            result=windows_native_snapshot(device,runner=runner)
        self.assertTrue(result['native_hdd_corrob'])
        self.assertEqual(commands[0][1]['timeout'],9)
        self.assertEqual(commands[0][0][-2:],['--number','4'])

    def test_native_probe_timeout_and_foreign_platform(self):
        with mock.patch.object(native_media.sys,'platform','linux'):
            self.assertIsNone(windows_native_snapshot(drive()))
        with mock.patch.object(native_media.sys,'platform','win32'):
            self.assertIsNone(windows_native_snapshot(drive(),runner=mock.Mock(
                side_effect=subprocess.TimeoutExpired('disk',9))))

    def test_ui_candidate_still_requires_engine(self):
        d=drive()
        public=d.public()
        report=interpret_native_evidence(d,native())
        ok,why=ui_repair_readiness(public,'carequick',snapshot=report)
        self.assertTrue(ok)
        self.assertIn('engine',why.lower())

    def test_guarded_requires_explicit_unknown_health_ack(self):
        report=interpret_native_evidence(drive(),native())
        args=Namespace(command='care-external',journal_backend='disk',journal='/healthy/journal',
                       rewrite_neighbors=False,recording='auto',ack_unknown_health=False,
                       max_regions=16,auto_lock_volumes=True,ack_media_warning=False)
        with mock.patch.object(release_policy,'REPAIR_BETA_GUARDED',True):
            with self.assertRaisesRegex(PermissionError,'ack-unknown-health'):
                check_guarded_repair_preflight(args,report,drive())
            args.ack_unknown_health=True
            advice=check_guarded_repair_preflight(args,report,drive())
            self.assertTrue(advice['can_attempt_hdd_refresh'])
            args.max_regions=64
            with self.assertRaisesRegex(PermissionError,'16'):
                check_guarded_repair_preflight(args,report,drive())
            args.max_regions=16
            unsafe={**report,'status':'failure_reported'}
            with self.assertRaises(PermissionError):
                check_guarded_repair_preflight(args,unsafe,drive())
            for item in ({**report,'native_hdd_corrob':False},
                         {**report,'source':'windows_storage_healthstatus'}):
                with self.assertRaises(PermissionError):
                    check_guarded_repair_preflight(args,item,drive())


if __name__=='__main__':
    unittest.main()
