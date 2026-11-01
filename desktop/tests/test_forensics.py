import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from driverepair_desktop.forensics import image_evidence_manifest


class EvidenceTests(unittest.TestCase):
    def test_readonly_manifest_hashes_real_content_and_redacts_path(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'case_sensitive_filename.img'
            src.write_bytes(b'forensic image data' * 256)
            before = src.read_bytes()
            out = Path(td) / 'case-report.json'
            report = image_evidence_manifest(str(src), str(out), case_ref='CASE-012')
            self.assertEqual(report['source_sha256'], hashlib.sha256(before).hexdigest())
            self.assertEqual(json.loads(out.read_text())['source_sha256'], report['source_sha256'])
            self.assertEqual(src.read_bytes(), before)
            self.assertNotIn(str(src), out.read_text())
            self.assertEqual(report['chain_of_custody'], 'NOT_CERTIFIED')
            # POSIX owner-only bits are meaningful on Unix; Windows does not preserve them.
            if sys.platform != 'win32':
                self.assertEqual(out.stat().st_mode & 0o077, 0)

    def test_never_overwrite_existing_report(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'image'
            src.write_bytes(b'x')
            report = Path(td) / 'report'
            report.write_text('old')
            with self.assertRaises(FileExistsError):
                image_evidence_manifest(str(src), str(report))
            self.assertEqual(report.read_text(), 'old')

    def test_rejects_symlinked_image(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'image'
            src.write_bytes(b'x')
            link = Path(td) / 'link'
            link.symlink_to(src)
            with self.assertRaises(ValueError):
                image_evidence_manifest(str(link), str(Path(td) / 'out'))

if __name__ == '__main__':
    unittest.main()
