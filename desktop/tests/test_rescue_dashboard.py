"""Regression coverage for professional rescue telemetry (no physical disks)."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from driverepair_desktop.cli import run
from driverepair_desktop.rescue_display import (
    RescueDisplayState, RescueTerminal, rescue_event, destination_free_space,
    format_duration,
)


class RescuePresentationTests(unittest.TestCase):
    def test_map_does_not_claim_unscanned_sectors_good(self):
        total = 1024 * 1024
        view = rescue_event({"cursor": 1024, "recovered_bytes": 1024,
                             "missing_ranges": [], "status": "in_progress"},
                            total=total, phase="FORWARD", destination="out.img", cells=16)
        self.assertEqual(view['map'][0], '?')
        self.assertEqual(view['map'][1:], '.' * 15)
        self.assertEqual(view['processed_bytes'], 1024)

    def test_map_keeps_missing_regions_unknown(self):
        view = rescue_event({"cursor": 4096, "recovered_bytes": 3072,
                             "missing_ranges": [[1024, 1024]], "failed_read_attempts": 2,
                             "status": "completed_with_missing_data"},
                            total=4096, phase="FORWARD", destination="out.img", cells=4)
        self.assertEqual(view['map'], 'oXoo')
        self.assertEqual(view['unreadable_bytes'], 1024)
        self.assertEqual(view['missing_regions'], 1)
        self.assertEqual(view['failed_reads'], 2)

    def test_retry_pending_also_counts_as_not_yet_recovered(self):
        view = rescue_event({"cursor": 4096, "recovered_bytes": 3072,
                             "missing_ranges": [], "retry_pending_ranges": [[0, 1024]]},
                            total=4096, phase="RETRY", destination="out.img", cells=4)
        self.assertEqual(view['map'], 'Xooo')
        self.assertEqual(view['unreadable_bytes'], 1024)

    def test_rate_and_eta_use_monotonic_elapsed_not_cursor_bytes_per_callback(self):
        moments = iter([0.0, 1.0, 2.0, 3.0])
        state = RescueDisplayState(clock=lambda: next(moments))
        base = {'phase': 'FORWARD', 'total_bytes': 4000}
        v0 = state.update({**base, 'processed_bytes': 1000})
        self.assertIsNone(v0['eta_seconds'])
        v1 = state.update({**base, 'processed_bytes': 2000})
        self.assertEqual(int(v1['speed_bytes_per_sec']), 1000)
        self.assertEqual(int(v1['eta_seconds']), 2)
        v2 = state.update({**base, 'phase': 'RETRY', 'processed_bytes': 4000})
        self.assertIsNone(v2['eta_seconds'])

    def test_rounded_duration_and_free_space(self):
        self.assertEqual(format_duration(3661), '1h 1m')
        with tempfile.TemporaryDirectory() as td:
            self.assertIsInstance(destination_free_space(str(Path(td) / 'new.img')), int)

    def test_non_tty_output_is_sparse_and_not_raw_cursor_lines(self):
        clock = iter([0., 0., 0., 1., 1., 2., 2., 62., 62.])
        stream = io.StringIO()
        panel = RescueTerminal(stream=stream, tty=False, clock=lambda: next(clock))
        base = {'phase': 'FORWARD', 'total_bytes': 10240, 'recovered_bytes': 100,
                'unreadable_bytes': 0}
        panel.show({**base, 'processed_bytes': 100})
        panel.show({**base, 'processed_bytes': 1024})
        panel.show({**base, 'processed_bytes': 2048})
        panel.show({**base, 'processed_bytes': 3072})
        self.assertEqual(len(stream.getvalue().splitlines()), 2)
        self.assertNotIn('RESCUE  cursor=', stream.getvalue())

    def test_rescue_cli_jsonl_is_machine_readable_and_image_exact(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'src.img'
            dst = Path(td) / 'dst.img'
            data = b'ABCD' * (512 * 1024)
            src.write_bytes(data)
            out = io.StringIO()
            err = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = run(['rescue-image', '--image', str(src), '--output', str(dst),
                            '--progress-jsonl', '--no-live-dashboard', '--json'])
            self.assertEqual(code, 0)
            self.assertEqual(dst.read_bytes(), data)
            self.assertEqual(json.loads(out.getvalue())['status'], 'completed')
            lines = [ln for ln in err.getvalue().splitlines() if ln.strip()]
            self.assertTrue(lines, err.getvalue())
            self.assertTrue(all(json.loads(ln)['type'] == 'progress' for ln in lines))
            event = json.loads(lines[-1])
            self.assertEqual(event['processed_bytes'], len(data))
            self.assertEqual(event['recovered_bytes'], len(data))
            self.assertEqual(event['unreadable_bytes'], 0)
            self.assertEqual(event['workflow'], 'rescue')
            self.assertEqual(len(event['map']), 512)


if __name__ == '__main__':
    unittest.main()
