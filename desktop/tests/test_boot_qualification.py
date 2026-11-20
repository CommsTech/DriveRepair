"""Synthetic ISO filesystem/catalog qualification. No physical media touched."""
import tempfile
from pathlib import Path
import unittest

from driverepair_desktop.boot_validation import qualify_live_iso

BLOCK=2048

def _record(name: bytes, lba: int, length: int, isdir=False):
    b=bytearray(33+len(name)+(0 if len(name)%2 else 1))
    b[0]=len(b)
    b[2:6]=lba.to_bytes(4,'little')
    b[6:10]=lba.to_bytes(4,'big')
    b[10:14]=length.to_bytes(4,'little')
    b[14:18]=length.to_bytes(4,'big')
    b[25]=2 if isdir else 0
    b[28:30]=(1).to_bytes(2,'little')
    b[30:32]=(1).to_bytes(2,'big')
    b[32]=len(name)
    b[33:33+len(name)]=name
    return bytes(b)

def _catalog_entry(platform):
    e=bytearray(32)
    e[0]=0x88
    e[8:12]=(60).to_bytes(4,'little')
    return e

def create_test_iso(path: Path, *, omit_rootfs=False, omit_efi=False):
    d=bytearray(256*BLOCK)
    d[510:512]=b'\x55\xaa'
    d[446+4]=0x17
    d[446+8:446+12]=(0).to_bytes(4,'little')
    d[446+12:446+16]=(256*4).to_bytes(4,'little')
    pvd=bytearray(BLOCK)
    pvd[:7]=b'\x01CD001\x01'
    pvd[156:190]=_record(b'\0',40,BLOCK,True)
    d[16*BLOCK:17*BLOCK]=pvd
    desc=bytearray(BLOCK)
    desc[:7]=b'\0CD001\x01'
    desc[7:39]=b'EL TORITO SPECIFICATION'.ljust(32,b' ')
    desc[71:75]=(20).to_bytes(4,'little')
    d[17*BLOCK:18*BLOCK]=desc
    d[18*BLOCK:18*BLOCK+7]=b'\xffCD001\x01'
    validation=bytearray(32)
    validation[0]=1
    validation[1]=0
    validation[30:32]=b'\x55\xaa'
    checksum=(-sum(int.from_bytes(validation[x:x+2],'little') for x in range(0,32,2)))&0xffff
    validation[28:30]=checksum.to_bytes(2,'little')
    catalog=bytearray(BLOCK)
    catalog[:32]=validation
    catalog[32:64]=_catalog_entry(0)
    catalog[64]=0x91
    catalog[65]=0xef
    if not omit_efi:
        catalog[96:128]=_catalog_entry(0xef)
    d[20*BLOCK:21*BLOCK]=catalog
    root=bytearray(BLOCK)
    records=[_record(b'\0',40,BLOCK,True),_record(b'\1',40,BLOCK,True),
             _record(b'LIVE',41,BLOCK,True)]
    root[:sum(map(len,records))]=b''.join(records)
    d[40*BLOCK:41*BLOCK]=root
    files=[b'VMLINUZ',b'INITRD.IMG']
    if not omit_rootfs:
        files.append(b'FILESYSTEM.SQUASHFS')
    live=bytearray(BLOCK)
    live_records=[_record(x,50+i,128) for i,x in enumerate(files)]
    live[:sum(map(len,live_records))]=b''.join(live_records)
    d[41*BLOCK:42*BLOCK]=live
    path.write_bytes(d)

class QualificationTests(unittest.TestCase):
    def test_reject_fake_iso_only_signatures(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'DriveRepair-Live-amd64.iso'
            data=bytearray(131072)
            data[510:512]=b'\x55\xaa'
            data[16*BLOCK:16*BLOCK+7]=b'\x01CD001\x01'
            src.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'hybrid disk'):
                qualify_live_iso(src)
    def test_real_components_required(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'DriveRepair-Live-amd64.iso'
            create_test_iso(src,omit_rootfs=True)
            with self.assertRaisesRegex(ValueError,'squashfs'):
                qualify_live_iso(src)
            create_test_iso(src,omit_efi=True)
            with self.assertRaisesRegex(ValueError,'UEFI'):
                qualify_live_iso(src)
    def test_structurally_complete_is_not_boot_certificate(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'DriveRepair-Live-amd64.iso'
            create_test_iso(src)
            result=qualify_live_iso(src)
            self.assertEqual(result['status'],'LIVE_CONTENTS_AND_BOOT_ENTRIES_PRESENT_BOOT_UNTESTED')
            self.assertTrue(result['bios_catalog'])
            self.assertTrue(result['uefi_catalog'])

if __name__=='__main__':
    unittest.main()
