import json
import tempfile
import unittest
from pathlib import Path

from driverepair_desktop.integrity import build_manifest, audit_image, restore_image_from_reference


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.baseline = self.root / 'original.img'
        self.candidate = self.root / 'candidate.img'
        self.manifest = self.root / 'manifest.json'
        self.chunk = 1024 * 1024
        source = b'A' * self.chunk + b'B' * self.chunk + b'C' * 512
        self.baseline.write_bytes(source)
        self.candidate.write_bytes(source)
        build_manifest(str(self.baseline), str(self.manifest), chunk_mib=1)

    def test_matches_unattested_manifest(self):
        r = audit_image(str(self.candidate), str(self.manifest))
        self.assertEqual(r['status'], 'matches_unattested_manifest')
        self.assertEqual(r['hash_matched_chunks'], 3)

    def test_detects_single_bit_and_targets_one_chunk(self):
        with self.candidate.open('r+b') as f:
            f.seek(self.chunk + 17)
            f.write(b'C')  # 0x42 -> 0x43, one bit flipped
        r = audit_image(str(self.candidate), str(self.manifest))
        self.assertEqual(r['status'], 'integrity_mismatch')
        self.assertEqual(r['hash_mismatched_chunks'], 1)
        self.assertEqual(r['mismatched_regions'][0]['offset'], self.chunk)
        self.assertEqual(r['hash_matched_chunks'], 2)

    def test_restores_new_copy_only_from_verified_reference(self):
        with self.candidate.open('r+b') as f:
            f.seek(self.chunk + 17)
            f.write(b'C')
        repaired = self.root / 'repaired.img'
        r = restore_image_from_reference(str(self.candidate), str(self.baseline), str(self.manifest), str(repaired))
        self.assertEqual(r['status'], 'verified_restored_copy')
        self.assertEqual(r['replaced_chunks'], 1)
        self.assertEqual(repaired.read_bytes(), self.baseline.read_bytes())
        self.assertNotEqual(self.candidate.read_bytes(), self.baseline.read_bytes())

    def test_bad_reference_not_treated_as_fixed(self):
        with self.candidate.open('r+b') as f:
            f.seek(0)
            f.write(b'X')
        bad = self.root / 'bad.img'
        bad.write_bytes(self.baseline.read_bytes())
        with bad.open('r+b') as f:
            f.seek(0)
            f.write(b'Z')
        repaired = self.root / 'repaired.img'
        r = restore_image_from_reference(str(self.candidate), str(bad), str(self.manifest), str(repaired))
        self.assertEqual(r['status'], 'incomplete_unverified_copy')
        self.assertEqual(r['unverified_chunks'], 1)
        self.assertEqual(repaired.read_bytes(), self.candidate.read_bytes())

    def test_rescue_holes_not_misreported_as_bit_flips(self):
        # Existing recovery map says 1MiB in middle is unreadable (not corrupt).
        journal = {'schema': 1, 'size': len(self.candidate.read_bytes()), 'sector': 512,
                   'cursor': len(self.candidate.read_bytes()),
                   'recovered_bytes': len(self.candidate.read_bytes()) - self.chunk,
                   'missing_ranges': [[self.chunk, self.chunk]], 'status': 'completed_with_missing_data',
                   'output': str(self.candidate)}
        Path(str(self.candidate) + '.rescue.json').write_text(json.dumps(journal))
        with self.candidate.open('r+b') as f:
            f.seek(self.chunk)
            f.write(b'Z')
        r = audit_image(str(self.candidate), str(self.manifest))
        self.assertEqual(r['unknown_chunks'], 1)
        self.assertEqual(r['hash_mismatched_chunks'], 0)
        with self.assertRaisesRegex(ValueError, 'unknown/unreadable'):
            restore_image_from_reference(str(self.candidate), str(self.baseline), str(self.manifest), str(self.root / 'repaired.img'))

    def test_bad_manifest_or_overwrite_refused(self):
        m = json.loads(self.manifest.read_text())
        m['chunks'][0] = 'xyz'
        self.manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, 'Malformed'):
            audit_image(str(self.candidate), str(self.manifest))
        with self.assertRaises(FileExistsError):
            build_manifest(str(self.baseline), str(self.manifest))

    def test_identity_and_output_guards(self):
        with self.assertRaisesRegex(ValueError, 'Reference cannot'):
            restore_image_from_reference(str(self.baseline), str(self.baseline), str(self.manifest), str(self.root / 'copy.img'))
        with self.assertRaises(FileExistsError):
            restore_image_from_reference(str(self.candidate), str(self.baseline), str(self.manifest), str(self.baseline))

if __name__ == '__main__':
    unittest.main()

class IntegrityCommandTests(unittest.TestCase):
    def test_cli_detects_and_repairs_only_known_changed_chunk(self):
        import contextlib
        import io
        from driverepair_desktop.cli import run
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            truth, candidate = d / 'truth.img', d / 'candidate.img'
            truth.write_bytes(b'A' * 1024 * 1024 + b'B' * 512)
            candidate.write_bytes(b'A' * 1024 * 1024 + b'C' * 512)
            manifest = d / 'truth.json'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run(['integrity-baseline', '--image', str(truth), '--output', str(manifest), '--json']), 0)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(run(['integrity-audit', '--image', str(candidate), '--manifest', str(manifest), '--json']), 2)
            self.assertEqual(json.loads(out.getvalue())['hash_mismatched_chunks'], 1)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(run(['integrity-restore-copy', '--image', str(candidate),
                                      '--reference', str(truth), '--manifest', str(manifest),
                                      '--output', str(d / 'fixed.img'), '--json']), 1)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(run(['integrity-restore-copy', '--image', str(candidate),
                                      '--reference', str(truth), '--manifest', str(manifest),
                                      '--output', str(d / 'fixed.img'), '--ack-same-snapshot', '--json']), 0)
            self.assertEqual(json.loads(out.getvalue())['replaced_chunks'], 1)
            self.assertEqual((d / 'fixed.img').read_bytes(), truth.read_bytes())
