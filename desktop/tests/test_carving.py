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

    def test_mp4_ftyp_box_walk(self):
        # Minimal contiguous ISO BMFF: ftyp + free + mdat with payload.
        ftyp = struct.pack('>I', 20) + b'ftyp' + b'isom' + struct.pack('>I', 0) + b'isom'
        free = struct.pack('>I', 16) + b'free' + b'\x00' * 8
        mdat = struct.pack('>I', 24) + b'mdat' + b'V' * 16
        blob = ftyp + free + mdat
        with open(self.image, 'wb') as f:
            f.write(b'\x00' * 32 + blob + b'\xff' * 64)
        result = carve_image(self.image, self.out, formats=('mp4',), max_file_mib=1)
        self.assertEqual(result['files_carved'], 1)
        entry = result['files'][0]
        self.assertEqual(entry['offset_bytes'], 32)
        self.assertEqual(entry['confidence'], 'mp4_ftyp_brand_and_box_walk')
        self.assertTrue(entry['filename'].endswith('.mp4'))
        with open(os.path.join(self.out, entry['filename']), 'rb') as f:
            self.assertEqual(f.read(), blob)

    def test_mp4_unknown_brand_rejected(self):
        ftyp = struct.pack('>I', 20) + b'ftyp' + b'zzzz' + struct.pack('>I', 0) + b'zzzz'
        mdat = struct.pack('>I', 16) + b'mdat' + b'XXXX'
        with open(self.image, 'wb') as f:
            f.write(ftyp + mdat)
        result = carve_image(self.image, self.out, formats=('mp4',))
        self.assertEqual(result['files_carved'], 0)

    def test_pdf_header_and_eof(self):
        pdf = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n'
        with open(self.image, 'wb') as f:
            f.write(b'\x00' * 16 + pdf + b'\x00' * 32)
        result = carve_image(self.image, self.out, formats=('pdf',))
        self.assertEqual(result['files_carved'], 1)
        entry = result['files'][0]
        self.assertEqual(entry['format'], 'pdf')
        self.assertTrue(entry['filename'].endswith('.pdf'))
        with open(os.path.join(self.out, entry['filename']), 'rb') as f:
            self.assertEqual(f.read(), pdf)

    def test_ole_doc_classified_by_stream_name(self):
        # Minimal 512-byte CFB header (sector shift 9) + WordDocument marker.
        header = bytearray(512)
        header[0:8] = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
        struct.pack_into('<H', header, 30, 9)
        struct.pack_into('<I', header, 44, 1)
        payload = bytes(header) + b'W\x00o\x00r\x00d\x00D\x00o\x00c\x00u\x00m\x00e\x00n\x00t\x00' + b'\x00' * 1024
        with open(self.image, 'wb') as f:
            f.write(payload)
        result = carve_image(self.image, self.out, formats=('ole',), max_file_mib=1)
        self.assertEqual(result['files_carved'], 1)
        self.assertEqual(result['files'][0]['format'], 'doc')
        self.assertTrue(result['files'][0]['filename'].endswith('.doc'))

if __name__ == '__main__':
    unittest.main()
