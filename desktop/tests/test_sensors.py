"""Soft sensor suite: acoustic WATCH, IMU shock STOP, SMART deltas."""
from __future__ import annotations

import contextlib
import io
import unittest

from driverepair_desktop.sensors import (
    AcousticWatcher,
    SensorSuite,
    ShockGuard,
    SmartDeltaTracker,
)


class SmartDeltaTests(unittest.TestCase):
    def test_baseline_then_watch_on_increase(self):
        tracker = SmartDeltaTracker()
        first = tracker.ingest({"ata.197": 0, "ata.5": 1, "ignored": 9})
        self.assertEqual(first[0].severity, "info")
        self.assertEqual(first[0].kind, "smart_delta")
        second = tracker.ingest({"ata.197": 2, "ata.5": 1})
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0].severity, "watch")
        self.assertIn("ata.197", second[0].message)

    def test_no_event_when_stable(self):
        tracker = SmartDeltaTracker()
        tracker.ingest({"nvme.media_errors": 3})
        self.assertEqual(tracker.ingest({"nvme.media_errors": 3}), [])


class ShockGuardTests(unittest.TestCase):
    def test_stop_when_over_threshold(self):
        guard = ShockGuard(threshold_g=1.5)
        guard.set_reader(lambda: 2.0)
        event = guard.poll(offset_bytes=4096)
        self.assertIsNotNone(event)
        self.assertEqual(event.severity, "stop")
        self.assertEqual(event.offset_bytes, 4096)

    def test_quiet_when_under_threshold(self):
        guard = ShockGuard(threshold_g=1.5)
        guard.set_reader(lambda: 1.0)
        self.assertIsNone(guard.poll())


class AcousticWatcherTests(unittest.TestCase):
    def test_unavailable_without_backend(self):
        watcher = AcousticWatcher()
        # Without sounddevice, poll should stay quiet / unavailable (not FAIL).
        if not watcher.available:
            self.assertIsNone(watcher.poll())


class SensorSuiteTests(unittest.TestCase):
    def test_suite_correlates_offset_and_stop(self):
        suite = SensorSuite(acoustic=False, shock=True, smart_deltas=True)
        suite.shock.set_reader(lambda: 3.0)
        suite.note_offset(8192)
        suite.ingest_smart_counters({"ata.198": 0})
        suite.ingest_smart_counters({"ata.198": 1})
        suite.poll()
        self.assertTrue(suite.should_stop())
        summary = suite.public_summary()
        self.assertTrue(summary["shock_available"])
        self.assertTrue(summary["smart_deltas_enabled"])
        self.assertTrue(any(e["severity"] == "stop" for e in summary["events"]))
        self.assertTrue(any(e["severity"] == "watch" for e in summary["events"]))
        self.assertIn("soft indicators", summary["notes"].lower())

    def test_cli_flags_present(self):
        from driverepair_desktop.cli import parser
        top = parser().format_help()
        self.assertIn("detect-filesystems", top)
        self.assertIn("recover-image", top)
        buf = io.StringIO()
        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stdout(buf):
                parser().parse_args(["refresh-external", "--help"])
        self.assertEqual(raised.exception.code, 0)
        help_text = buf.getvalue()
        self.assertIn("--acoustic-watch", help_text)
        self.assertIn("--shock-guard", help_text)
        self.assertIn("--smart-deltas", help_text)


if __name__ == "__main__":
    unittest.main()
