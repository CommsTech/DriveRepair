"""Windows UASP USB HDDs must pass the same independent external disk gate."""
import json
import unittest
from unittest import mock
from driverepair_desktop.devices import Device, assert_windows_external_write_gate


def dev():
    return Device('windows:PhysicalDrive4',r'\\.\PhysicalDrive4','ST1000LM048',
                  1000204886016,512,'usb','SN0001')


def run_case(*, get_bus='SCSI', native_bus='USB', native_size=1000204886016,
             is_boot=False, is_system=False, is_offline=False, gate_serial='SN0001'):
    calls=[]
    def run(args,timeout=None):
        text=' '.join(args).lower()
        calls.append(text)
        if 'get-disk' in text:
            return json.dumps({'Number':4,'BusType':get_bus,'FriendlyName':'Seagate',
                'SerialNumber':gate_serial,'Size':1000204886016,'LogicalSectorSize':512,
                'IsBoot':is_boot,'IsSystem':is_system,'IsOffline':is_offline}).encode()
        if 'inspect-windows-disk' in text:
            return json.dumps({'number':4,'bus':native_bus,'size_bytes':native_size}).encode()
        raise AssertionError('Unexpected subprocess')
    return run, calls


class UASPGateTests(unittest.TestCase):
    def test_independent_native_usb_admits_uasp_with_system_gates(self):
        runner,calls=run_case()
        with mock.patch('driverepair_desktop.devices.sys.platform','win32'):
            assert_windows_external_write_gate(dev(), runner)
        self.assertTrue(any('inspect-windows-disk' in call for call in calls))

    def test_uasp_internal_sas_and_mismatched_size_not_admitted(self):
        for kw in ({'native_bus':'SAS'}, {'native_size':1000204886016+256*1024*1024},
                   {'is_boot':True}, {'is_system':True}, {'is_offline':True},
                   {'gate_serial':'OTHER-DRIVE'}):
            with self.subTest(kw=kw):
                runner,_=run_case(**kw)
                with mock.patch('driverepair_desktop.devices.sys.platform','win32'):
                    with self.assertRaises(RuntimeError):
                        assert_windows_external_write_gate(dev(),runner)

    def test_plain_usb_does_not_need_extra_probe(self):
        runner,calls=run_case(get_bus='USB')
        with mock.patch('driverepair_desktop.devices.sys.platform','win32'):
            assert_windows_external_write_gate(dev(),runner)
        self.assertFalse(any('inspect-windows-disk' in c for c in calls))

if __name__=='__main__':
    unittest.main()
