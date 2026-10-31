import errno
import os
import tempfile
import unittest
from unittest.mock import patch

from driverepair_desktop.scanner import ImageReader, scan_offsets, scan_reader


class FakeReader:
    def __init__(self, data: bytes, fails: set[int] | None = None):
        self.data = data
        self.fails = fails or set()
        self.calls = []
    def read_at(self, offset, count):
        self.calls.append((offset, count))
        if offset in self.fails:
            raise OSError(errno.EIO, "injected I/O error")
        return self.data[offset:offset+count]
    def close(self):
        pass


class ScannerTests(unittest.TestCase):
    def test_sample_offsets_never_overlap(self):
        offsets = list(scan_offsets(1024 * 1024, 512, "sample", 30))
        self.assertEqual(len(offsets), 30)
        self.assertEqual(len({offset for offset, _ in offsets}), 30)
        self.assertEqual(offsets[0][0], 0)
        self.assertEqual(offsets[-1][0], 1024 * 1024 - 512)

    def test_full_clean_scan(self):
        src = FakeReader(bytes(range(256)) * 16)
        result = scan_reader(src, size=4096, sector=512, mode="full", chunk=1024)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["readable_bytes"], 4096)
        self.assertEqual(result["attempted_chunks"], 4)
        self.assertEqual(src.calls, [(0, 1024), (1024, 1024), (2048, 1024), (3072, 1024)])

    def test_error_is_not_success_and_scan_stops_bounded(self):
        src = FakeReader(b"a" * 8192, fails={0, 1024, 2048})
        result = scan_reader(src, size=8192, sector=512, mode="full", chunk=1024, max_errors=2)
        self.assertEqual(result["status"], "aborted_error_limit")
        self.assertEqual(result["read_error_chunks"], 2)
        self.assertEqual(result["readable_bytes"], 0)
        self.assertEqual(result["attempted_chunks"], 2)
        self.assertEqual(result["read_error_ranges"][0]["offset"], 0)

    def test_short_read_is_not_success(self):
        src = FakeReader(b"a" * 512)
        result = scan_reader(src, size=1024, sector=512, mode="full", chunk=1024)
        self.assertEqual(result["status"], "completed_with_read_errors")
        self.assertEqual(result["readable_bytes"], 0)

    def test_device_disconnection_aborts(self):
        src = FakeReader(b"a" * 4096)
        def disconnected(offset, count):
            raise OSError(errno.ENODEV, "unplugged")
        src.read_at = disconnected
        result = scan_reader(src, size=4096, sector=512, mode="full", chunk=1024)
        self.assertEqual(result["status"], "aborted_device_or_access_error")
        self.assertEqual(result["attempted_chunks"], 1)

    def test_4kn_alignment_rejects_tiny_chunk(self):
        with self.assertRaises(ValueError):
            scan_reader(FakeReader(b"a" * 4096), size=4096, sector=4096,
                        chunk=512, mode="full")

    def test_regular_file_image_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            image = os.path.join(td, "image.bin")
            with open(image, "wb") as f:
                f.write(b"a" * 4096)
            with open(image, "rb") as file:
                before = file.read()
            reader = ImageReader(image)
            try:
                result = scan_reader(reader, size=4096, sector=512,
                                     chunk=1024, mode="full")
            finally:
                reader.close()
            self.assertEqual(result["status"], "completed")
            with open(image, "rb") as file:
                self.assertEqual(before, file.read())

    def test_invalid_scan_arguments_fail_closed(self):
        for kwargs in (dict(size=0), dict(sector=0), dict(chunk=513), dict(max_errors=0)):
            options = dict(size=4096, sector=512, chunk=1024, mode="full")
            options.update(kwargs)
            with self.assertRaises(ValueError):
                scan_reader(FakeReader(b"a" * 4096), **options)


if __name__ == "__main__":
    unittest.main()
