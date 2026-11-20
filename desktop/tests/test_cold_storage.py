"""Cold-storage file-level bit-integrity regression tests (no physical disk needed)."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from driverepair_desktop.cold_storage import (
    create_baseline, audit_archive, write_html_report,
)
from driverepair_desktop.cli import run


class ColdStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.archive = self.base / 'family-photos'
        self.archive.mkdir()
        (self.archive / '2001').mkdir()
        (self.archive / '2001' / 'photo.jpg').write_bytes(b'\xff\xd8\x00JPEG\xff\xd9')
        (self.archive / '2001' / 'video.mov').write_bytes(b'video\0' * 1000)
        self.manifest = self.base / 'snapshot-2026.json'

    def baseline(self):
        result = create_baseline(str(self.archive), str(self.manifest))
        self.assertEqual(result['status'], 'baseline_created_unattested')
        return result

    def test_detects_one_bit_with_no_second_image(self):
        original = (self.archive / '2001' / 'photo.jpg').read_bytes()
        self.baseline()
        self.assertEqual(audit_archive(str(self.archive), str(self.manifest))['status'], 'matches_baseline')
        (self.archive / '2001' / 'photo.jpg').write_bytes(original[:-1] + b'\xd8')
        result = audit_archive(str(self.archive), str(self.manifest))
        self.assertEqual(result['files_changed'], 1)
        self.assertEqual(result['files_unchanged'], 1)
        self.assertEqual(result['status'], 'integrity_alert')
        self.assertEqual(result['changed'][0]['path'], '2001/photo.jpg')
        self.assertEqual((self.archive / '2001' / 'photo.jpg').read_bytes(),original[:-1]+b'\xd8')

    def test_added_and_missing_not_confused_with_corruption(self):
        self.baseline()
        (self.archive / 'new-photo.jpg').write_bytes(b'more photos')
        out = audit_archive(str(self.archive), str(self.manifest))
        self.assertEqual(out['status'], 'new_files_found')
        self.assertEqual(out['files_new'], 1)
        self.assertEqual(out['files_changed'], 0)
        (self.archive / '2001' / 'video.mov').unlink()
        out = audit_archive(str(self.archive), str(self.manifest))
        self.assertEqual(out['status'], 'integrity_alert')
        self.assertEqual(out['files_missing'], 1)
        self.assertEqual(out['files_new'], 1)
        self.assertEqual(out['files_changed'], 0)

    def test_refuses_baseline_on_unreadable_symlink(self):
        outside = self.base / 'outside.txt'
        outside.write_text('NOT to be hashed')
        try:
            (self.archive / 'link.txt').symlink_to(outside)
        except (NotImplementedError, OSError):
            self.skipTest('Symlink privileges unavailable')
        with self.assertRaisesRegex(RuntimeError,'Baseline not written'):
            self.baseline()
        self.assertFalse(self.manifest.exists())

    def test_rejects_baseline_overwrite_or_inside_archive(self):
        with self.assertRaisesRegex(ValueError,'OUTSIDE'):
            create_baseline(str(self.archive), str(self.archive/'inside.json'))
        self.baseline()
        with self.assertRaises(FileExistsError):
            create_baseline(str(self.archive), str(self.manifest))

    def test_manifest_traversal_rejected(self):
        self.baseline()
        m=json.loads(self.manifest.read_text(encoding='utf-8'))
        m['files'][0]['path'] = '../outside'
        self.manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,'Unsafe path'):
            audit_archive(str(self.archive), str(self.manifest))

    def test_create_readable_html_with_no_source_mutation(self):
        self.baseline()
        # Windows rejects <> in filenames; use & to still prove HTML escaping.
        (self.archive / 'new & photo.jpg').write_bytes(b'new')
        report = audit_archive(str(self.archive), str(self.manifest))
        outfile=self.base/'integrity.html'
        written=Path(write_html_report(report,str(outfile),str(self.archive)))
        self.assertEqual(written.resolve(), outfile.resolve())
        html=outfile.read_text(encoding='utf-8')
        self.assertIn('Cold Storage Integrity',html)
        self.assertIn('new &amp; photo.jpg',html)
        self.assertNotIn('new & photo.jpg',html)
        with self.assertRaises(FileExistsError):
            write_html_report(report,str(outfile),str(self.archive))

    def test_exact_cli_read_only_baseline_verify(self):
        with contextlib.redirect_stdout(io.StringIO()) as out,contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run(['archive-baseline','--folder',str(self.archive),
                                  '--output',str(self.manifest),'--json']),0)
        self.assertEqual(json.loads(out.getvalue())['files_baselined'],2)
        report=self.base/'report.html'
        with contextlib.redirect_stdout(io.StringIO()) as out,contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run(['archive-verify','--folder',str(self.archive),
                                  '--manifest',str(self.manifest),'--report-html',str(report),'--json']),0)
        self.assertEqual(json.loads(out.getvalue())['status'],'matches_baseline')
        self.assertTrue(report.exists())
        (self.archive / '2001' / 'photo.jpg').write_bytes(b'changed')
        with contextlib.redirect_stdout(io.StringIO()) as out,contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run(['archive-verify','--folder',str(self.archive),
                                  '--manifest',str(self.manifest),'--json']),2)
        self.assertEqual(json.loads(out.getvalue())['files_changed'],1)

    def test_manifest_after_move_drive_letter_works(self):
        self.baseline()
        moved=self.base/'reconnected-drive'
        self.archive.rename(moved)
        self.assertEqual(audit_archive(str(moved),str(self.manifest))['status'],'matches_baseline')


if __name__=='__main__':
    unittest.main()

class IsoBuildDependencyTests(unittest.TestCase):
    def test_wsl_installs_python_for_structural_verification(self):
        from driverepair_desktop.windows_iso_build import _WSL_BUILD_SCRIPT
        self.assertIn('command -v python3',_WSL_BUILD_SCRIPT)
        self.assertIn('live-build debootstrap xorriso python3',_WSL_BUILD_SCRIPT)
