import io
import json
import time
import unittest

from driverepair_desktop.progress_events import ProgressEmitter
from driverepair_desktop.refresh_display import RefreshDashboard


class ProgressEmitterTests(unittest.TestCase):
    def test_disabled_emits_nothing(self):
        buf = io.StringIO()
        ProgressEmitter(enabled=False, stream=buf).emit({"phase": "PROBE"})
        self.assertEqual(buf.getvalue(), "")

    def test_throttle_and_force(self):
        buf = io.StringIO()
        emitter = ProgressEmitter(enabled=True, stream=buf, min_interval_s=10.0)
        emitter.emit({"phase": "A"})
        emitter.emit({"phase": "B"})  # throttled
        emitter.emit({"phase": "C"}, force=True)
        lines = [ln for ln in buf.getvalue().splitlines() if ln]
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        self.assertEqual(first["type"], "progress")
        self.assertEqual(first["phase"], "A")
        self.assertEqual(second["phase"], "C")

    def test_dashboard_forwards_to_emitter(self):
        buf = io.StringIO()
        emitter = ProgressEmitter(enabled=True, stream=buf, min_interval_s=0.0)
        dash = RefreshDashboard(mode="adaptive", size=1024, enabled=False, emitter=emitter)
        dash.handle({
            "status": "probing",
            "probe_index": 1,
            "probe_total": 8,
            "offset": 0,
            "message": "probe",
        })
        lines = [ln for ln in buf.getvalue().splitlines() if ln]
        self.assertGreaterEqual(len(lines), 1)
        event = json.loads(lines[-1])
        self.assertEqual(event["type"], "progress")
        self.assertIn("health", event)
        self.assertIn("map", event)
        self.assertEqual(event["probe_index"], 1)

    def test_interval_allows_second_emit(self):
        buf = io.StringIO()
        emitter = ProgressEmitter(enabled=True, stream=buf, min_interval_s=0.01)
        emitter.emit({"n": 1})
        time.sleep(0.02)
        emitter.emit({"n": 2})
        lines = [ln for ln in buf.getvalue().splitlines() if ln]
        self.assertEqual(len(lines), 2)


class CliProgressFlagTests(unittest.TestCase):
    def test_progress_jsonl_flag_registered(self):
        from driverepair_desktop.cli import parser as build_cli
        args = build_cli().parse_args([
            "refresh-image", "--image", "x.img", "--journal", "j",
            "--ack-risk", "--ack-destructive", "--ack-no-backup", "--ack-data-loss-risk",
            "--progress-jsonl", "--no-live-dashboard",
        ])
        self.assertTrue(args.progress_jsonl)
        self.assertFalse(args.live_dashboard)


if __name__ == "__main__":
    unittest.main()
