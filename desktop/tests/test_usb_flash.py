"""Synthetic USB flash contract tests; no real block device is touched."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from driverepair_desktop.devices import Device
from driverepair_desktop.usb_flash import inspect_hybrid_iso, validate_target, flash_usb_iso


class FakeDisk:
    def __init__(self, capacity, *, corrupt=False, short=False):
        self.bytes=bytearray(capacity)
        self.closed=False
        self.corrupt=corrupt
        self.short=short
        self.write_calls=0

    def write_at(self, off, data):
        self.write_calls+=1
        count=len(data)-512 if self.short else len(data)
        self.bytes[off:off+count]=data[:count]
        return count

    def read_at(self, off, n):
        data=bytes(self.bytes[off:off+n])
        if self.corrupt and off==0:
            return b'!' + data[1:]
        return data

    def flush(self): pass
    def close(self): self.closed=True


def _synthetic_usb_device() -> Device:
    """Platform-shaped fake identity so validate_target can run off-hardware."""
    if sys.platform == 'win32':
        return Device('windows:PhysicalDrive99', r'\\.\PhysicalDrive99',
                      'Sacrificial USB', 3 * 1024 * 1024, 512, 'usb',
                      'real_serial_9811')
    return Device('linux:/dev/sdz', '/dev/sdz', 'Sacrificial USB', 3 * 1024 * 1024,
                  512, 'usb', 'real_serial_9811')


class USBFlashTests(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.image=Path(td.name)/'DriveRepair-live.iso'
        payload=bytearray(os.urandom(144005))
        payload[510:512]=b'\x55\xaa'
        payload[16*2048+1:16*2048+6]=b'CD001'
        self.image.write_bytes(payload)
        self.device=_synthetic_usb_device()
        self.correct={'expect_fingerprint':self.device.fingerprint[:12],
                      'typed_confirmation':'ERASE '+self.device.id,
                      'acknowledge_data_loss':True}
        self._gate = patch('driverepair_desktop.usb_flash.assert_windows_external_write_gate')
        self._gate.start()
        self.addCleanup(self._gate.stop)

    def test_hybrid_gate_and_explicit_consent(self):
        self.assertEqual(inspect_hybrid_iso(self.image)['bytes'],144005)
        with self.assertRaises(PermissionError):
            validate_target(self.device,144005,expect_fingerprint='wrong',
                            typed_confirmation=self.correct['typed_confirmation'])
        with self.assertRaises(PermissionError):
            validate_target(self.device,144005,expect_fingerprint=self.correct['expect_fingerprint'],
                            typed_confirmation='ERASE linux:/dev/sdb')
        with self.assertRaises(PermissionError):
            flash_usb_iso(str(self.image),self.device.id,selected_device=self.device,
                          acknowledge_data_loss=False,expect_fingerprint=self.correct['expect_fingerprint'],
                          typed_confirmation=self.correct['typed_confirmation'])
        self.image.write_bytes(b'not an iso')
        with self.assertRaises(ValueError):
            inspect_hybrid_iso(self.image)

    def test_reject_system_bus_and_too_small_usb(self):
        internal=Device(self.device.id,self.device.path,self.device.model,
                        self.device.size_bytes,512,'sata',self.device.serial)
        with self.assertRaises(PermissionError):
            validate_target(internal,144005,expect_fingerprint=internal.fingerprint[:12],
                            typed_confirmation='ERASE '+internal.id)
        with self.assertRaises(ValueError):
            validate_target(self.device,self.device.size_bytes+512,**{
                'expect_fingerprint':self.correct['expect_fingerprint'],
                'typed_confirmation':self.correct['typed_confirmation']})

    def run_flash(self, disk, **kw):
        events=[]
        with patch('driverepair_desktop.usb_flash._source_elsewhere'):
            result=flash_usb_iso(str(self.image),self.device.id,
                selected_device=self.device, target_opener=lambda _:disk,
                progress=events.append,**(self.correct|kw))
        return result,events

    def test_writes_padded_image_and_full_readback(self):
        disk=FakeDisk(self.device.size_bytes)
        result,events=self.run_flash(disk)
        self.assertEqual(result['status'],'USB_FLASH_BYTE_VERIFIED_BOOT_UNTESTED')
        self.assertEqual(disk.bytes[:144005],self.image.read_bytes())
        self.assertEqual(disk.bytes[144005:result['written_bytes']],b'\0'*(result['written_bytes']-144005))
        self.assertTrue(disk.closed)
        self.assertEqual(events[-1]['phase'],'DONE')
        self.assertEqual([e['phase'] for e in events if e['phase'] in {'WRITING','VERIFYING'}][0],'WRITING')

    def test_corrupt_readback_refuses_success_and_closes(self):
        disk=FakeDisk(self.device.size_bytes,corrupt=True)
        with patch('driverepair_desktop.usb_flash._source_elsewhere'):
            events=[]
            # PermissionError subclasses OSError; require a real I/O failure class.
            with self.assertRaises(OSError) as ctx:
                flash_usb_iso(str(self.image),self.device.id,selected_device=self.device,
                    target_opener=lambda _:disk,progress=events.append,**self.correct)
            self.assertNotIsInstance(ctx.exception, PermissionError)
        self.assertTrue(disk.closed)
        self.assertEqual(events[-1]['phase'],'FAILED')
        self.assertFalse(any(e['phase']=='DONE' for e in events))

    def test_short_write_fails_and_closes(self):
        disk=FakeDisk(self.device.size_bytes,short=True)
        with self.assertRaises(OSError) as ctx:
            self.run_flash(disk)
        self.assertNotIsInstance(ctx.exception, PermissionError)
        self.assertTrue(disk.closed)

    def test_stop_boundary_fails_not_success(self):
        disk=FakeDisk(self.device.size_bytes)
        with patch('driverepair_desktop.usb_flash._source_elsewhere'):
            events=[]
            with self.assertRaises(InterruptedError):
                flash_usb_iso(str(self.image),self.device.id,selected_device=self.device,
                    target_opener=lambda _:disk,progress=events.append,
                    should_stop=lambda:True,**self.correct)
        self.assertEqual(disk.write_calls,0)
        self.assertEqual(events[-1]['phase'],'FAILED')


if __name__=='__main__':
    unittest.main()
