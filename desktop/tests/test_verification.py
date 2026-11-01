import json
import tempfile
import unittest
from pathlib import Path

from driverepair_desktop.verification import verify_images


class VerificationTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.a = Path(t.name) / 'original.img'
        self.b = Path(t.name) / 'copy.img'
        self.a.write_bytes(b'abc' * 5000)
        self.b.write_bytes(self.a.read_bytes())

    def test_exact_bytewise(self):
        result = verify_images(str(self.a), str(self.b))
        self.assertEqual(result['status'], 'verified_byte_exact')
        self.assertEqual(result['source_sha256'], result['candidate_sha256'])

    def test_corruption_found(self):
        with open(self.b, 'r+b') as f:
            f.seek(250)
            f.write(b'X')
        result = verify_images(str(self.a), str(self.b))
        self.assertEqual(result['status'], 'data_mismatch')
        self.assertEqual(result['first_mismatch_offset'], 250)

    def test_incomplete_rescue_rejected_even_if_zeros_match(self):
        Path(str(self.b) + '.rescue.json').write_text(json.dumps({
            'status': 'completed_with_missing_data', 'missing_ranges': [[0, 512]]}))
        result = verify_images(str(self.a), str(self.b))
        self.assertEqual(result['status'], 'incomplete_recovery_map')

    def test_mismatched_size(self):
        self.b.write_bytes(b'abc')
        self.assertEqual(verify_images(str(self.a), str(self.b))['status'], 'size_mismatch')

    def test_same_file_refused(self):
        with self.assertRaises(ValueError):
            verify_images(str(self.a), str(self.a))

if __name__ == '__main__':
    unittest.main()
