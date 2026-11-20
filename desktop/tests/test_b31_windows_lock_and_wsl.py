"""Regression checks: raw disk sharing, lock lifetime, and WSL startup issues."""
import subprocess
import unittest
from unittest.mock import patch

from driverepair_desktop.devices import Device
from driverepair_desktop.media_refresh import (WindowsReadWriter,
                                                 _windows_lock_paths)
from driverepair_desktop import windows_iso_build as wsl


class _API:
    """Mockable ctypes-style API callable (supports argtypes/restype)."""
    def __init__(self, name, fn, calls):
        self.name, self.fn, self.calls = name, fn, calls

    def __call__(self, *args):
        self.calls.append((self.name, args))
        return self.fn(*args)


class _Kernel:
    def __init__(self):
        self.calls=[]
        self.CreateFileW=_API('open', lambda *args: 200 if 'PhysicalDrive' in args[0] else 100,
                              self.calls)
        self.CloseHandle=_API('close', lambda *args: 1, self.calls)
        self.DeviceIoControl=_API('ioctl', lambda *args: 1, self.calls)


class WindowsVolumeLockRegressions(unittest.TestCase):
    def new_writer(self):
        writer=WindowsReadWriter.__new__(WindowsReadWriter)
        writer._device=Device('windows:PhysicalDrive3', r'\\.\PhysicalDrive3',
                              'Synthetic external HDD', 1024 * 1024, 512, 'usb', 'UNITTEST1234')
        writer.kernel=_Kernel()
        writer.handle=None
        writer._volume_handles=[]
        return writer

    def test_raw_disk_share_read_write_during_held_lock(self):
        writer=self.new_writer()
        writer._volume_handles=[100]
        writer.open_raw()
        self.assertEqual(writer.handle,200)
        op=[args for name,args in writer.kernel.calls if name=='open'][0]
        self.assertEqual(op[2],3, 'Windows raw handle must coexist with system storage handles')
        self.assertEqual(op[1],0xC0000000)
        self.assertEqual(op[5],0x80000000, 'Keep write-through')
        writer.close()
        self.assertEqual([args[0] for name,args in writer.kernel.calls if name=='close'],
                         [200,100], 'Raw writer must close before the last volume lock')

    def test_partial_acquisition_cleanup_on_second_lock_failure(self):
        writer=self.new_writer()
        attempts=[]
        def lock_or_fail(*args):
            attempts.append(args[1])
            # First partition lock and dismount succeeded; second partition lock fails.
            return args[0] == 100
        writer.kernel.CreateFileW=_API('open', lambda *args: 100 if 'E:' in args[0] else 101,
                                        writer.kernel.calls)
        writer.kernel.DeviceIoControl=_API('ioctl', lock_or_fail,writer.kernel.calls)
        parts=[{'PartitionNumber':1,'Type':'Basic','GptType':'','Paths':['E:\\']},
               {'PartitionNumber':2,'Type':'Basic','GptType':'','Paths':['F:\\']}]
        with patch('driverepair_desktop.media_refresh._windows_partition_inventory',return_value=parts), \
             patch('driverepair_desktop.media_refresh.ctypes.get_last_error',return_value=32,create=True):
            with self.assertRaisesRegex(RuntimeError,'FSCTL_LOCK_VOLUME'):
                try:
                    writer.lock_volumes(3,allow_mounted=True)
                finally:
                    writer.close()
        self.assertIsNone(writer.handle)
        self.assertEqual(writer._volume_handles,[])
        self.assertIn(('close',(100,)),writer.kernel.calls)

    def test_guids_do_not_bypass_mounted_authorization(self):
        paths=[{'Paths':["E:" + chr(92), chr(92)*2 + "?" + chr(92) + "Volume{12}" + chr(92)]}]
        with self.assertRaisesRegex(RuntimeError,'explicit|authorization'):
            _windows_lock_paths(paths, allow_mounted=False)


class WSLStartupRegressions(unittest.TestCase):
    def test_path_conversion_does_not_spawn_linux_vm(self):
        self.assertEqual(wsl._standard_wsl_mount(r'C:\Users\Public\drive rescue'),
                         '/mnt/c/Users/Public/drive rescue')
        self.assertEqual(wsl._standard_wsl_mount(r'D:\builds\test'),'/mnt/d/builds/test')
        self.assertIsNone(wsl._standard_wsl_mount(r'\\server\share\build'))
        with self.assertRaisesRegex(ValueError,'Unsafe'):
            wsl._standard_wsl_mount(r'C:\Users\..\System32')

    def test_installed_debian_does_not_trigger_another_install(self):
        class Response:
            returncode=0
            stdout='Ubuntu\nDebian\n'.encode('utf-16-le')
        with patch.object(wsl.sys,'platform','win32'):
            self.assertIsNone(wsl.require_debian_wsl(runner=lambda *a,**k:Response()))

    def test_unavailable_wsl_does_not_propose_duplicate_install(self):
        def timeout(*args,**kwargs):
            raise subprocess.TimeoutExpired(['wsl.exe','--list'], 18)
        with patch.object(wsl.sys,'platform','win32'):
            with self.assertRaises(wsl.WSLPrerequisiteError) as caught:
                wsl.require_debian_wsl(runner=timeout)
            self.assertFalse(caught.exception.missing_distro)

    def test_missing_debian_is_distinct(self):
        class Response:
            returncode=0
            stdout='Ubuntu\n'
        with patch.object(wsl.sys,'platform','win32'):
            with self.assertRaises(wsl.WSLPrerequisiteError) as caught:
                wsl.require_debian_wsl(runner=lambda *a,**k:Response())
            self.assertTrue(caught.exception.missing_distro)


if __name__ == '__main__':
    unittest.main()
