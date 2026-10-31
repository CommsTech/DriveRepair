import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from driverepair_desktop.cli import run
from driverepair_desktop.devices import Device


class CLITests(unittest.TestCase):
    def test_image_scan_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "sample.img")
            with open(p, "wb") as f:
                f.write(b"k" * 4096)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = run(["scan-image", "--image", p, "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.getvalue())["status"], "completed")

    def test_full_hardware_scan_requires_ack(self):
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            code = run(["scan", "--device", "linux:/dev/sdb", "--mode", "full"])
        self.assertEqual(code, 1)
        self.assertIn("--ack-risk", out.getvalue())

    def test_new_device_identity_rejected(self):
        original = Device("linux:/dev/sdb", "/dev/sdb", "USB", 4096, 512, "usb", "old")
        changed = Device("linux:/dev/sdb", "/dev/sdb", "USB", 4096, 512, "usb", "new")
        out = io.StringIO()
        with patch("driverepair_desktop.cli.select_external_device", side_effect=[original, changed]):
            with contextlib.redirect_stderr(out):
                code = run(["scan", "--device", original.id])
        self.assertEqual(code, 1)
        self.assertIn("identity changed", out.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
