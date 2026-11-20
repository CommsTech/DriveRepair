import unittest
from pathlib import Path
from unittest.mock import patch

from driverepair_desktop.scan_followup import checked_ranges, recheck_errors
from driverepair_desktop.windows_iso_build import wsl_path, require_debian_wsl, WSLPrerequisiteError
from driverepair_desktop.dependencies import smartctl_path

DEVICE = {'identity_hint': '123456789abc', 'model': 'Synthetic HDD',
          'size_bytes': 16*1024, 'sector_size': 512}
SCAN = {'device': DEVICE.copy(), 'device_size_bytes': DEVICE['size_bytes'],
        'logical_sector_bytes':512, 'read_error_chunks':1,
        'read_error_ranges':[{'offset':1024, 'length':1024}]}

class Reader:
    def __init__(self):
        self.calls=[]

    def read_at(self, offset, count):
        self.calls.append((offset,count))
        return b'G'*count

class ScanFollowupTests(unittest.TestCase):
    def test_unchanged_fingerprint_required(self):
        bad=dict(DEVICE, identity_hint='wrong')
        with self.assertRaisesRegex(ValueError, 'another device'):
            checked_ranges(SCAN,bad)

    def test_geometry_must_match(self):
        with self.assertRaisesRegex(ValueError, 'Geometry'):
            checked_ranges(SCAN,dict(DEVICE,size_bytes=8192))

    def test_rejects_malformed_offset(self):
        with self.assertRaisesRegex(ValueError, 'Malformed'):
            checked_ranges(dict(SCAN, read_error_ranges=[{'offset':1025,'length':512}]),DEVICE)

    def test_only_prior_failed_ranges_are_read_without_writes(self):
        reader=Reader()
        report=recheck_errors(SCAN,DEVICE,reader,max_reads=8)
        self.assertEqual(report['status'],'read_only_suspect_recheck_completed')
        self.assertEqual(report['patient_writes'],0)
        self.assertEqual(report['verified_files'],0)
        self.assertTrue(reader.calls)
        self.assertTrue(all(1024 <= start < 2048 for start,length in reader.calls))
        self.assertEqual(len(report['repeatably_readable_ranges']),1)

    def test_recheck_does_not_claim_full_scan_or_repaired_lifespan(self):
        result=recheck_errors(SCAN,DEVICE,Reader())
        self.assertIn('No source sectors were repaired',result['message'])

class WSLTests(unittest.TestCase):
    def test_wsl_path_no_shell(self):
        class Response:
            returncode=0
            stdout='/mnt/c/drive/output\n'
            stderr=''
        seen=[]
        def fake(cmd,**kwargs):
            seen.append(cmd)
            return Response()
        # Pin the non-Windows branch so the runner contract (wslpath invocation
        # with no shell) is exercised platform-independently.
        with patch('driverepair_desktop.windows_iso_build.sys.platform','linux'):
            result=wsl_path(Path('/tmp/drive-output'),runner=fake)
        self.assertEqual(result,'/mnt/c/drive/output')
        self.assertEqual(seen[0][:5],['wsl.exe','-d','Debian','--exec','wslpath'])

    def test_wsl_path_windows_drive_mapping(self):
        # Windows branch maps standard drive-letter paths without spawning WSL.
        from unittest.mock import patch as _patch, MagicMock as _MagicMock
        from pathlib import PureWindowsPath
        fake_path = _MagicMock()
        fake_path.resolve.return_value = PureWindowsPath('C:/tmp/drive-output')
        with patch('driverepair_desktop.windows_iso_build.sys.platform','win32'), \
             _patch('driverepair_desktop.windows_iso_build.Path', return_value=fake_path):
            result=wsl_path('C:\\tmp\\drive-output')
        self.assertEqual(result,'/mnt/c/tmp/drive-output')

    def test_wsl_path_windows_rejects_non_drive_path(self):
        with patch('driverepair_desktop.windows_iso_build.sys.platform','win32'):
            with self.assertRaisesRegex(WSLPrerequisiteError,'/mnt/<drive>'):
                wsl_path('\\\\server\\share\\build')

    def test_distro_not_found(self):
        class Response:
            returncode=0
            stdout='Ubuntu\n'
        with patch('driverepair_desktop.windows_iso_build.sys.platform','win32'):
            with self.assertRaisesRegex(RuntimeError,'Debian WSL distribution'):
                require_debian_wsl(runner=lambda *a,**k:Response())

class BundledSmartTests(unittest.TestCase):
    def test_missing_bundled_binary_not_falsely_available(self):
        with patch('driverepair_desktop.dependencies.shutil.which',return_value=None), \
             patch('driverepair_desktop.dependencies.sys.platform','linux'):
            self.assertIsNone(smartctl_path())

if __name__=='__main__':
    unittest.main()
