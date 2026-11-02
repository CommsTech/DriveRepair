"""Real Tk workflow and packaged-engine regression tests; synthetic files only.

Run with: xvfb-run -a python -m unittest tests.test_gui_workflows -v
No physical device I/O is permitted: discovery is stubbed to an empty list.
"""
from __future__ import annotations

import hashlib
import os
import sys
import contextlib
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from driverepair_desktop.gui import recovery_command


class ProcessEntryPointTests(unittest.TestCase):
    def test_installed_package_uses_module_execution(self):
        self.assertEqual(
            recovery_command(['rescue-image', '--help'], executable='/python', entrypoint='/usr/bin/driverepair-gui'),
            ['/python', '-m', 'driverepair_desktop', 'rescue-image', '--help'],
        )

    def test_existing_portable_package_reenters_zipapp(self):
        with tempfile.TemporaryDirectory() as td:
            app = Path(td) / 'DriveRepair.pyz'
            app.touch()
            self.assertEqual(recovery_command(['scan-image', '--help'], executable='/python', entrypoint=str(app)),
                             ['/python', str(app), 'scan-image', '--help'])


try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    tk = None


def close_window(root):
    # Execute the window manager callback so the GUI cancels scheduled polls.
    root.tk.call(root.protocol('WM_DELETE_WINDOW'))


def all_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from all_widgets(child)


@unittest.skipIf(tk is None, 'Tk is not installed')
class RealGuiWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except tk.TclError:
            raise unittest.SkipTest('No display (use xvfb-run for GUI integration tests)')

    def open_app(self, scenario):
        from driverepair_desktop import gui, devices
        original_tk = tk.Tk
        errors: list[str] = []
        exceptions: list[str] = []

        def patched_tk(*args, **kwargs):
            root = original_tk(*args, **kwargs)
            root.report_callback_exception = lambda et, ev, tb: exceptions.append(str(ev))
            def runner():
                try:
                    scenario(root, errors)
                except Exception as exc:
                    errors.append(f'{type(exc).__name__}: {exc}')
                finally:
                    if root.winfo_exists():
                        close_window(root)
            root.after(300, runner)
            return root

        # Triggering workflows must never enumerate or read physical test-host disks.
        with mock.patch.object(tk, 'Tk', side_effect=patched_tk), \
             mock.patch.object(devices, 'list_external_devices', return_value=[]), \
             mock.patch.object(messagebox, 'showerror', side_effect=lambda title, text, **kw: errors.append(f'{title}: {text}')):
            gui.launch()
        self.assertFalse(exceptions, f'Unhandled Tk exceptions: {exceptions}')
        self.assertFalse(errors, f'GUI failures: {errors}')

    def test_all_seven_guided_workflow_buttons_open_tabs(self):
        expected = {
            'My computer will not boot / only one internal disk': 'Recover OS drive',
            'My files were accidentally deleted': 'Recover deleted files',
            'My external drive is slow or failing': 'Diagnose / Rescue',
            'I need a forensic working copy': 'Image recovery',
            'I suspect silent file corruption / flipped bits': 'Integrity / bit errors',
            'My filesystem is corrupted': 'Clone repair',
            'I want to refresh readable media': 'In-place refresh',
        }
        def scenario(root, errors):
            widgets = list(all_widgets(root))
            notebook = next(w for w in widgets if isinstance(w, ttk.Notebook))
            self.assertEqual(notebook.tab(notebook.select(), 'text').strip(), 'Start here')
            for label, tab in expected.items():
                button = next((w for w in widgets if isinstance(w, ttk.Button) and w.cget('text') == label), None)
                self.assertIsNotNone(button, label)
                button.invoke()
                root.update_idletasks()
                self.assertEqual(notebook.tab(notebook.select(), 'text').strip(), tab)
            # The tab headers themselves remain navigable, independently of the guided buttons.
            for tab_id in notebook.tabs():
                notebook.select(tab_id)
                root.update_idletasks()
                self.assertEqual(notebook.select(), tab_id)
        self.open_app(scenario)

    def test_idle_dashboard_is_collapsed_and_user_can_expand_it(self):
        def scenario(root, errors):
            root.update()
            widgets = list(all_widgets(root))
            notebook = next(w for w in widgets if isinstance(w, ttk.Notebook))
            self.assertTrue(bool(notebook.winfo_ismapped()) or bool(notebook.winfo_manager()))
            toggle = next(w for w in widgets if isinstance(w, ttk.Checkbutton)
                          and w.cget('text') == 'Show recovery dashboard')
            # The overview owns the "DATA SAVED TO IMAGE" metric card.
            label = next(w for w in widgets if isinstance(w, tk.Label) and
                         w.cget('text') == 'DATA SAVED TO IMAGE')
            overview = label.master.master.master
            self.assertFalse(bool(overview.winfo_manager()),
                             'Idle dashboard should not crowd out Start Here')
            toggle.invoke()
            root.update()
            self.assertTrue(bool(overview.winfo_manager()),
                            'Dashboard toggle should reveal progress controls')
            toggle.invoke()
            root.update()
            self.assertFalse(bool(overview.winfo_manager()))
        self.open_app(scenario)

    def test_drive_workflow_shows_action_buttons(self):
        def scenario(root, errors):
            widgets = list(all_widgets(root))
            button = next(w for w in widgets if isinstance(w, ttk.Button) and w.cget('text') == 'My external drive is slow or failing')
            button.invoke()
            root.update_idletasks()
            for text in ('Refresh inventory', 'SMART', 'Quick scan', 'Full scan', 'Benchmark', 'Rescue (Linux/Windows)'):
                target = next(w for w in widgets if isinstance(w, ttk.Button) and w.cget('text') == text)
                self.assertTrue(target.winfo_ismapped(), f'{text} is hidden after navigation')
        self.open_app(scenario)

    def test_quick_scan_requires_an_explicit_selected_drive(self):
        def scenario(root, errors):
            widgets = list(all_widgets(root))
            navigate = next(w for w in widgets if isinstance(w, ttk.Button)
                            and w.cget('text') == 'My external drive is slow or failing')
            navigate.invoke()
            quick = next(w for w in widgets if isinstance(w, ttk.Button)
                         and w.cget('text') == 'Quick scan')
            with mock.patch.object(messagebox, 'showerror') as show:
                quick.invoke()
                show.assert_called_once()
                self.assertIn('Select an external drive', show.call_args.args[1])
        self.open_app(scenario)

    def test_image_recovery_gui_to_cli_produces_exact_bytes(self):
        from driverepair_desktop import gui, devices
        original_tk = tk.Tk
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'patient.img'
            dst = Path(td) / 'restored.img'
            src.write_bytes((bytes(range(256)) * 4096) + b'end-of-image')
            errors: list[str] = []
            completed = [False]

            def patched_tk(*args, **kwargs):
                root = original_tk(*args, **kwargs)
                def begin():
                    try:
                        widgets = list(all_widgets(root))
                        navigate = next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text') == 'I need a forensic working copy')
                        navigate.invoke()
                        nb = next(w for w in widgets if isinstance(w,ttk.Notebook))
                        self.assertEqual(nb.tab(nb.select(),'text').strip(),'Image recovery')
                        container = root.nametowidget(nb.select())
                        entries = [w for w in all_widgets(container) if isinstance(w,ttk.Entry)]
                        self.assertGreaterEqual(len(entries),3)
                        entries[0].insert(0,str(src))
                        entries[1].insert(0,str(dst))
                        action = next(w for w in all_widgets(container) if isinstance(w,ttk.Button) and w.cget('text') == 'Rescue')
                        action.invoke()
                    except Exception as exc:
                        errors.append(str(exc)); close_window(root); return
                    check(time.monotonic()+12)
                def check(deadline):
                    if errors or time.monotonic() > deadline:
                        errors.append('Rescue did not complete in time' if not errors else '')
                        close_window(root); return
                    # Sparse/preallocated images can reach their FINAL LOGICAL SIZE
                    # before recovery commits any bytes. Journal, not file length,
                    # is the authoritative completion criterion.
                    if dst.exists():
                        from driverepair_desktop.recovery import inspect_rescue_status
                        try:
                            state = inspect_rescue_status(str(dst))
                        except (OSError, ValueError, RuntimeError):
                            state = {}
                        if state.get('clean_rescue_complete'):
                            if hashlib.sha256(dst.read_bytes()).digest() == hashlib.sha256(src.read_bytes()).digest():
                                completed[0] = True
                            else:
                                errors.append('Output bytes mismatch despite completed recovery journal')
                            # Give the GUI poller time to process result and disable Stop.
                            root.after(250, lambda: close_window(root))
                            return
                    root.after(100, lambda: check(deadline))
                root.after(350, begin)
                return root

            # In subprocess mode, module import is resolved from current desktop working dir.
            portable = os.environ.get('DRIVEREPAIR_SMOKE_PYZ')
            override = (mock.patch.object(sys, 'argv', [str(Path(portable).resolve()), 'gui'])
                        if portable else contextlib.nullcontext())
            with override, \
                 mock.patch.object(tk, 'Tk', side_effect=patched_tk), \
                 mock.patch.object(devices, 'list_external_devices', return_value=[]), \
                 mock.patch.object(messagebox,'showerror',side_effect=lambda a,b,**kw: errors.append(f'{a}: {b}')):
                gui.launch()
            self.assertFalse(errors, errors)
            self.assertTrue(completed[0], 'GUI rescue did not produce byte-identical output')


if __name__ == '__main__':
    unittest.main()
