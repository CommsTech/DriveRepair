import struct
import unittest
from driverepair_desktop.windows_native import decode_descriptor, decode_alignment, probe_physicaldrive

class WindowsNativeTests(unittest.TestCase):
    def test_native_descriptor_ignores_unsafe_offsets(self):
        data=bytearray(120)
        struct.pack_into('<II',data,0,36,120)
        struct.pack_into('<IIIII',data,12,36,45,60,65,7)
        data[36:42]=b'ADATA\0'
        data[45:53]=b'SSD-123\0'
        data[60:65]=b'V1.0\0'
        data[65:73]=b'PRIVATE\0'
        x=decode_descriptor(bytes(data))
        self.assertEqual(x['bus'],'USB')
        self.assertEqual(x['model'],'SSD-123')
        self.assertEqual(x['firmware_revision'],'V1.0')
        self.assertEqual(x['serial'],'PRIVATE')
        self.assertFalse(x['removable_media'])
        struct.pack_into('<I',data,24,999999)
        self.assertIsNone(decode_descriptor(bytes(data))['serial'])

    def test_alignment(self):
        data=bytearray(28)
        struct.pack_into('<II',data,0,28,28)
        struct.pack_into('<II',data,16,512,4096)
        self.assertEqual(decode_alignment(bytes(data))['physical_sector_bytes'],4096)
        struct.pack_into('<I',data,16,0)
        with self.assertRaises(ValueError):
            decode_alignment(bytes(data))

    def test_not_a_windows_write_bypass(self):
        import sys
        if sys.platform=='win32':
            return
        with self.assertRaisesRegex(RuntimeError,'Windows-only'):
            probe_physicaldrive(2)

if __name__=='__main__':
    unittest.main()
