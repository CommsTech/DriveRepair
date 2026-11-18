"""Fault-injection around independent byte-for-byte post-rewrite checks."""
import hashlib
from unittest import TestCase
from driverepair_desktop.postverify import verify_committed_regions


class Reader:
    def __init__(self, data, *, mutate_second=False, fail=False):
        self.data = data
        self.reads = 0
        self.mutate_second = mutate_second
        self.fail = fail

    def read_at(self, offset, count):
        self.reads += 1
        if self.fail:
            raise OSError('device unplugged')
        part = self.data[offset:offset + count]
        if self.mutate_second and self.reads == 2:
            return bytes([part[0] ^ 1]) + part[1:]
        return part


class PostVerifyTests(TestCase):
    def setUp(self):
        self.data = b'alpha' * 512 + b'beta' * 640  # 5120 bytes
        self.records = [[0, 2560, hashlib.sha256(self.data[:2560]).hexdigest()],
                        [2560, 2560, hashlib.sha256(self.data[2560:]).hexdigest()]]

    def test_full_exact_digest_twice_passes(self):
        reader = Reader(self.data)
        result = verify_committed_regions(reader, self.records, size=5120, sector=512)
        self.assertEqual(result['status'], 'postverify_passed')
        self.assertEqual(result['verified_bytes'], 5120)
        self.assertEqual(reader.reads, 4)

    def test_media_changed_after_flush_detected(self):
        corrupted = bytearray(self.data)
        corrupted[123] ^= 1
        result = verify_committed_regions(Reader(corrupted), self.records, size=5120, sector=512)
        self.assertEqual(result['status'], 'postverify_failed')
        self.assertEqual(result['failures'][0]['classification'], 'preimage_digest_mismatch')

    def test_inconsistent_read_detected(self):
        result = verify_committed_regions(Reader(self.data, mutate_second=True),
                                           self.records, size=5120, sector=512)
        self.assertEqual(result['failures'][0]['classification'], 'inconsistent_readback')

    def test_unplugged_device_is_not_a_success(self):
        result = verify_committed_regions(Reader(self.data, fail=True),
                                           self.records, size=5120, sector=512)
        self.assertEqual(result['status'], 'postverify_failed')
        self.assertEqual(result['verified_bytes'], 0)

    def test_journal_ranges_fail_closed(self):
        for records in ([], [[0,512,'0'*64], [0,512,'0'*64]],
                        [[5120,512,'0'*64]], [[0,1024,'X'*64]],
                        [[0,512,'0'*64], [256,512,'0'*64]]):
            with self.subTest(records=records), self.assertRaises(ValueError):
                verify_committed_regions(Reader(self.data), records, size=5120, sector=512)

    def test_no_unbounded_journal_or_io(self):
        with self.assertRaises(ValueError):
            verify_committed_regions(Reader(self.data), self.records, size=5120,
                                     sector=512, max_bytes=2048)
