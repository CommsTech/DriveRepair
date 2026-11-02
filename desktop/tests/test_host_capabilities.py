import pathlib
import tempfile
import unittest
from driverepair_desktop.host_capabilities import linux_properties, inspect_readonly

class HostCapabilitiesTests(unittest.TestCase):
    def test_linux_properties_no_guess_from_rotational(self):
        with tempfile.TemporaryDirectory() as folder:
            base=pathlib.Path(folder)
            q=base/'sdb'/'queue';q.mkdir(parents=True)
            for k,v in {'rotational':'1','zoned':'none','max_sectors_kb':'1024',
                        'logical_block_size':'512','physical_block_size':'4096'}.items():
                (q/k).write_text(v)
            data=linux_properties('sdb',sys_root=base)
            self.assertEqual(data['rotational'],True)
            self.assertEqual(data['max_request_kib'],1024)
            self.assertEqual(data['physical_sector_bytes'],4096)
            self.assertNotIn('cmr',data)
            self.assertFalse(data['write_authorized'])
    def test_reject_device_id_injection(self):
        with self.assertRaises(ValueError):inspect_readonly('linux:/dev/sda;rm -rf /', platform='linux')
        with self.assertRaises(ValueError):inspect_readonly('windows:PhysicalDrive2 && echo fail',platform='win32')

if __name__ == '__main__':unittest.main()
