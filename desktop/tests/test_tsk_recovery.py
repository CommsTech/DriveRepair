"""Optional TSK adapter: mock CLI and verify command injection safety + selection."""
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from driverepair_desktop.tsk_recovery import list_deleted_tsk, recover_selected_tsk


FLS = 'r/r * 70-128-1: deleted/alpha.txt\nr/r * 71-128-1: deleted/../beta.jpg\n'


class FakeProcess:
    def __init__(self, args, **kwargs):
        self.args = args
        self.returncode = 0
        if args[0] == 'fls':
            self.stdout = io.StringIO(FLS)
        elif args[0] == 'icat':
            self.stdout = io.BytesIO(b'raw extracted content')
        else:
            raise RuntimeError('unexpected command')
    def kill(self):
        self.returncode = -9
    def wait(self, **kwargs):
        return self.returncode


class TskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.image = Path(self.tmp.name) / 'image.raw'
        self.image.write_bytes(b'\0' * 4096)
        self.out = Path(self.tmp.name) / 'recovered'
        self.runner = patch('driverepair_desktop.tsk_recovery.subprocess.Popen', side_effect=FakeProcess)
        self.which = patch('driverepair_desktop.tsk_recovery.shutil.which', side_effect=lambda s:s)
        self.runner.start(); self.which.start()
        self.addCleanup(self.runner.stop)
        self.addCleanup(self.which.stop)

    def test_selectively_extracts_only_requested_inode(self):
        before = hashlib.sha256(self.image.read_bytes()).digest()
        found = list_deleted_tsk(str(self.image))['candidates']
        self.assertEqual(len(found), 2)
        report = recover_selected_tsk(str(self.image), str(self.out),
                                      selected_ids=[found[1]['id']])
        self.assertEqual(report['files_recovered'], 1)
        recovered = list(self.out.glob('*'))
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].read_bytes(), b'raw extracted content')
        self.assertNotIn('..', recovered[0].name)
        self.assertEqual(before, hashlib.sha256(self.image.read_bytes()).digest())

    def test_missing_selected_id_fails_before_creating_output(self):
        with self.assertRaises(ValueError):
            recover_selected_tsk(str(self.image), str(self.out), selected_ids=['f'*20])
        self.assertFalse(self.out.exists())

    def test_symlinked_source_rejected(self):
        link = Path(self.tmp.name) / 'alias.raw'
        link.symlink_to(self.image)
        with self.assertRaises(ValueError):
            list_deleted_tsk(str(link))

if __name__ == '__main__':
    unittest.main()
