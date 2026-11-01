"""Journal-authoritative progress regression tests; use test images, no devices."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from driverepair_desktop.cli import run
from driverepair_desktop.recovery import inspect_rescue_status, _rescue_writer_lock, rescue_reader


class RecoveryStatusTests(unittest.TestCase):
    def _call(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = run(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_sparse_preallocated_image_is_not_a_completed_rescue(self):
        with tempfile.TemporaryDirectory() as td:
            src, dst = Path(td) / 'patient.img', Path(td) / 'output.img'
            src.write_bytes(b'A' * (4 * 1024 * 1024))
            code, _, _ = self._call(['rescue-image', '--image', str(src),
                                      '--output', str(dst), '--chunk-mib', '1',
                                      '--max-chunks', '1', '--no-live-dashboard'])
            self.assertEqual(code, 2)  # in progress
            self.assertEqual(dst.stat().st_size, 4 * 1024 * 1024)
            map_path = Path(str(dst) + '.rescue.json')
            before = map_path.read_bytes()
            code, printed, _ = self._call(['rescue-status', '--output', str(dst), '--json'])
            state = json.loads(printed)
            self.assertEqual(code, 2)
            self.assertFalse(state['clean_rescue_complete'])
            self.assertEqual(state['logical_image_size_bytes'], 4 * 1024 * 1024)
            self.assertEqual(state['cursor_bytes'], 1024 * 1024)
            self.assertEqual(state['unprocessed_bytes'], 3 * 1024 * 1024)
            self.assertEqual(state['percent_processed'], 25.0)
            self.assertEqual(map_path.read_bytes(), before, 'inspection must not mutate map')
            code, _, _ = self._call(['rescue-image', '--image', str(src),
                                      '--output', str(dst), '--chunk-mib', '1',
                                      '--resume', '--no-live-dashboard'])
            self.assertEqual(code, 0)
            code, printed, _ = self._call(['rescue-status', '--output', str(dst), '--json'])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(printed)['clean_rescue_complete'])

    def test_invalid_map_accounting_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            src, dst = Path(td) / 'patient.img', Path(td) / 'out.img'
            src.write_bytes(b'B' * 2048)
            code, _, _ = self._call(['rescue-image', '--image', str(src),
                                      '--output', str(dst), '--no-live-dashboard'])
            self.assertEqual(code, 0)
            map_path = Path(str(dst) + '.rescue.json')
            state = json.loads(map_path.read_text())
            state['recovered_bytes'] = -1
            map_path.write_text(json.dumps(state))
            with self.assertRaises(ValueError):
                inspect_rescue_status(str(dst))

    def test_missing_image_is_not_clean_even_with_completed_map(self):
        with tempfile.TemporaryDirectory() as td:
            src, dst = Path(td) / 'patient.img', Path(td) / 'out.img'
            src.write_bytes(b'C' * 4096)
            self._call(['rescue-image', '--image', str(src),
                        '--output', str(dst), '--no-live-dashboard'])
            dst.unlink()
            with self.assertRaises(OSError):
                inspect_rescue_status(str(dst))

    def test_second_writer_is_refused_and_lock_can_be_reacquired(self):
        with tempfile.TemporaryDirectory() as td:
            out = str(Path(td) / 'rescue.img')
            class Patient:
                def read_at(self, pos, n):
                    return b'Z' * n
            with _rescue_writer_lock(out):
                with self.assertRaisesRegex(RuntimeError, 'already running'):
                    rescue_reader(Patient(), size=4096, sector=512,
                                  output=out, source_token='test', chunk=512)
            result = rescue_reader(Patient(), size=4096, sector=512,
                                   output=out, source_token='test', chunk=512)
            self.assertEqual(result['status'], 'completed')
            self.assertTrue(Path(out + '.rescue.lock').exists())

    def test_private_lab_powershell_helpers_are_not_shipped(self):
        """Operator USB-dock helpers stay outside the product tree.

        False completion / auto-refresh hazards lived in those wrappers. The
        supported path is the CLI/GUI (``rescue-status``, explicit refresh acks).
        """
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        forbidden = (
            'run_elevated_samsung_pm841_lab.ps1',
            'resume_samsung_rescue_then_continue.ps1',
            'watch_and_continue_samsung_lab.ps1',
            'run_elevated_seagate_st1000_lab.ps1',
            'run_elevated_seagate_wipe_refresh.ps1',
            'run_elevated_adaptive_refresh.ps1',
            'run_elevated_live_lab.ps1',
        )
        for filename in forbidden:
            self.assertFalse(
                (scripts / filename).exists(),
                f'lab helper must not ship in product tree: {filename}',
            )
        # Directory may contain a short README only.
        leftovers = [p.name for p in scripts.glob('*.ps1')]
        self.assertEqual(leftovers, [], f'unexpected PowerShell leftovers: {leftovers}')


if __name__ == '__main__':
    unittest.main()
