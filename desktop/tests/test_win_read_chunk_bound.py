"""Pure-Python Win32 API double: never opens a patient disk."""
import ctypes
import unittest
from driverepair_desktop.scanner import WindowsReader

class FakeKernel:
    def __init__(self):
        self.pointer=0
        self.read_sizes=[]
        self.positions=[]
    def SetFilePointerEx(self, handle, position, reserved, method):
        self.pointer=int(position.value)
        self.positions.append(self.pointer)
        return True
    def ReadFile(self, handle, buffer, count, result_ptr, reserved):
        self.read_sizes.append(count)
        ctypes.memset(buffer, ord('A'), count)
        ctypes.cast(result_ptr, ctypes.POINTER(ctypes.c_ulong)).contents.value=count
        return True

class TestWinBoundedPhysicalRead(unittest.TestCase):
    def test_large_logical_scan_uses_small_usb_calls(self):
        inst=WindowsReader.__new__(WindowsReader)
        inst.handle=object()
        inst.kernel=FakeKernel()
        inst.max_transfer=1024*1024
        result=inst.read_at(512,2*1024*1024+8192)
        self.assertEqual(len(result),2*1024*1024+8192)
        self.assertEqual(inst.kernel.read_sizes,[1024*1024,1024*1024,8192])
        self.assertEqual(inst.kernel.positions,[512,512+1024*1024,512+2*1024*1024])
        self.assertEqual(result,b'A'*(2*1024*1024+8192))
    def test_rejects_invalid_offset_and_empty_read(self):
        inst=WindowsReader.__new__(WindowsReader)
        inst.handle=object()
        inst.kernel=FakeKernel()
        inst.max_transfer=1024*1024
        with self.assertRaises(ValueError):
            inst.read_at(-1,512)
        self.assertEqual(inst.read_at(0,0),b'')
        self.assertEqual(inst.kernel.read_sizes,[])

if __name__ == '__main__':
    unittest.main()
