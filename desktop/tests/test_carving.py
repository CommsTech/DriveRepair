import json
import os
import struct
import tempfile
import unittest
import zlib
from driverepair_desktop.carving import carve_image, PNG_SIG


def png_chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def tiny_png():
    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    return (PNG_SIG + png_chunk(b'IHDR', ihdr)
            + png_chunk(b'IDAT', zlib.compress(b'\x00\x00\x00\x00'))
            + png_chunk(b'IEND', b''))


class CarvingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.image = os.path.join(self.tmp.name, 'image.bin')
        self.out = os.path.join(self.tmp.name, 'carved')

    def test_valid_png_found_with_correct_crc(self):
        original = tiny_png()
        with open(self.image, 'wb') as f:
            f.write(b'X' * 100 + original + b'Z' * 500)
        result = carve_image(self.image, self.out)
        self.assertEqual(result['files_carved'], 1)
        entry = result['files'][0]
        self.assertEqual(entry['offset_bytes'], 100)
        self.assertEqual(entry['confidence'], 'png_chunk_crc_valid')
        with open(os.path.join(self.out, entry['filename']), 'rb') as f:
            self.assertEqual(f.read(), original)

    def test_png_bad_crc_not_claimed_recovered(self):
        damaged = bytearray(tiny_png())
        damaged[-5] ^= 0xff
        with open(self.image, 'wb') as f:
            f.write(damaged)
        result = carve_image(self.image, self.out)
        self.assertEqual(result['files_carved'], 0)

    def test_jpeg_heuristic_confidence(self):
        jpeg = b'\xff\xd8\xff\xe0' + b'1' * 96 + b'\xff\xd9'
        with open(self.image, 'wb') as f:
            f.write(b'123' + jpeg)
        result = carve_image(self.image, self.out)
        self.assertEqual(result['files_carved'], 1)
        self.assertEqual(result['files'][0]['confidence'], 'jpeg_signature_and_end_marker_only')

    def test_incomplete_rescue_map_refused_by_default(self):
        with open(self.image, 'wb') as f:
            f.write(tiny_png())
        with open(self.image + '.rescue.json', 'w') as f:
            json.dump({'status': 'completed_with_missing_data'}, f)
        with self.assertRaises(RuntimeError):
            carve_image(self.image, self.out)
        self.assertFalse(os.path.exists(self.out))
        result = carve_image(self.image, self.out, allow_incomplete=True)
        self.assertEqual(result['files_carved'], 1)

    def test_does_not_overwrite_existing_directory(self):
        with open(self.image, 'wb') as f:
            f.write(tiny_png())
        os.mkdir(self.out)
        with self.assertRaises(FileExistsError):
            carve_image(self.image, self.out)

if __name__ == '__main__':
    unittest.main()
