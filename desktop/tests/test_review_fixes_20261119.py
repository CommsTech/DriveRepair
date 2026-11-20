"""Regressions from the 2026-11-19 code-quality review.

- The rescue CLI printed JSON on both the --json and human paths, so there was
  no human output at all.
- scanner.scan_reader caught TypeError around the progress call, which also
  swallowed a TypeError raised *inside* the callback and retried with a
  different signature, hiding the real defect.
"""
import contextlib
import io
import os
import tempfile
import unittest

from driverepair_desktop.cli import run
from driverepair_desktop.scanner import scan_reader


class Reader:
    def __init__(self, data):
        self.data = data

    def read_at(self, offset, count):
        return self.data[offset:offset + count]

    def close(self):
        pass


class ProgressCallbackHonestyTests(unittest.TestCase):
    def test_callback_typeerror_is_not_masked(self):
        data = bytes(4096)

        def broken(index, total, info=None):
            raise TypeError('callback bug: bad arithmetic')

        with self.assertRaises(TypeError):
            scan_reader(Reader(data), size=len(data), sector=512, mode='triage',
                        samples=4, chunk=1024, progress=broken)

    def test_two_argument_callback_still_supported(self):
        seen = []

        def two_arg(index, total):
            seen.append((index, total))

        scan_reader(Reader(bytes(4096)), size=4096, sector=512, mode='triage',
                    samples=4, chunk=1024, progress=two_arg)
        self.assertTrue(seen)


class RescueHumanOutputTests(unittest.TestCase):
    def test_human_path_is_not_raw_json(self):
        with tempfile.TemporaryDirectory() as td:
            source = os.path.join(td, 'source.img')
            dest = os.path.join(td, 'rescue.img')
            with open(source, 'wb') as handle:
                handle.write(bytes(range(256)) * 16)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = run(['rescue-image', '--image', source,
                            '--output', dest])
            text = out.getvalue()
            self.assertEqual(code, 0, text)
            self.assertTrue(text.lstrip().startswith('Status:'),
                            f'human output should be a summary, got: {text[:120]}')
            self.assertNotIn('"schema"', text)

    def test_json_path_remains_machine_readable(self):
        with tempfile.TemporaryDirectory() as td:
            source = os.path.join(td, 'source.img')
            dest = os.path.join(td, 'rescue.img')
            with open(source, 'wb') as handle:
                handle.write(bytes(range(256)) * 16)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                run(['rescue-image', '--image', source, '--output', dest,
                     '--json'])
            import json
            parsed = json.loads(out.getvalue())
            self.assertEqual(parsed['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
