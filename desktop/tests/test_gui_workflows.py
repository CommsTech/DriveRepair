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
             mock.patch.object(gui, 'load_preferences', return_value={'schema': 1, 'repair_storage': 'disk', 'repair_policy': 'balanced', 'dashboard': False}), \
             mock.patch.object(gui, 'save_preferences', return_value=None), \
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
            for text in ('Refresh inventory', 'SMART', 'Quick repair', 'Full repair', 'Rescue to image'):
                target = next(w for w in widgets if isinstance(w, ttk.Button) and w.cget('text') == text)
                self.assertTrue(target.winfo_ismapped(), f'{text} is hidden after navigation')
            advanced = next(w for w in widgets if isinstance(w, ttk.Checkbutton)
                            and 'Advanced settings' in w.cget('text'))
            benchmark = next(w for w in widgets if isinstance(w, ttk.Button)
                             and w.cget('text') == 'Benchmark (read-only)')
            self.assertFalse(benchmark.winfo_ismapped())
            advanced.invoke()
            root.update_idletasks()
            self.assertTrue(benchmark.winfo_ismapped())
        self.open_app(scenario)

    def test_direct_repair_and_ram_only_options_are_visible(self):
        def scenario(root, errors):
            widgets = list(all_widgets(root))
            navigate = next(w for w in widgets if isinstance(w, ttk.Button)
                            and w.cget('text') == 'My external drive is slow or failing')
            navigate.invoke()
            root.update_idletasks()
            all_visible = list(all_widgets(root))
            labels = {str(w.cget('text')) for w in all_visible
                      if isinstance(w, ttk.Button)}
            self.assertIn('Quick repair', labels)
            self.assertIn('Full repair', labels)
            self.assertIn('Read-only quick check', labels)
            for name in ('Firmware info', 'Optimize advice', 'Investigate a failed offset (read-only)'):
                self.assertIn(name, labels)
            comboboxes = [w for w in all_visible if isinstance(w, ttk.Combobox)]
            match = [w for w in comboboxes if any('Volatile RAM only' in str(opt)
                     for opt in w.cget('values'))]
            self.assertTrue(match, 'RAM-only mode must be offered alongside disk journaling')
            self.assertTrue(match[0].winfo_ismapped(), 'RAM-only storage selector is hidden')
            self.assertIn('Disk journal', match[0].get())  # Safe first-run default
            match[0].set('Volatile RAM only (no recovery image/journal)')
            self.assertIn('Volatile RAM only', match[0].get())
            # This test intentionally does not select a real disk or authorize a write.
        self.open_app(scenario)

    def test_quick_scan_requires_an_explicit_selected_drive(self):
        def scenario(root, errors):
            widgets = list(all_widgets(root))
            navigate = next(w for w in widgets if isinstance(w, ttk.Button)
                            and w.cget('text') == 'My external drive is slow or failing')
            navigate.invoke()
            quick = next(w for w in widgets if isinstance(w, ttk.Button)
                         and w.cget('text') == 'Quick repair')
            with mock.patch.object(messagebox, 'showerror') as show:
                quick.invoke()
                show.assert_called_once()
                self.assertIn('Select an external drive', show.call_args.args[1])
        self.open_app(scenario)

    def test_map_legend_matches_color_cells_and_repair_policies_visible(self):
        def scenario(root, errors):
            widgets = list(all_widgets(root))
            for caption, expected in [('Not scanned', '#243041'),
                                      ('Read successfully', '#3fa76a'),
                                      ('In progress', '#5eb0ef'),
                                      ('Slow region', '#c47a20'),
                                      ('Needs investigation', '#d4a017'),
                                      ('Read error / unknown', '#d14949')]:
                title = next((w for w in widgets if isinstance(w, tk.Label)
                              and w.cget('text') == caption), None)
                self.assertIsNotNone(title, caption)
                swatch = next(w for w in title.master.winfo_children()
                              if w is not title and isinstance(w, tk.Label))
                self.assertEqual(swatch.cget('background').lower(), expected)
            nav = next(w for w in widgets if isinstance(w, ttk.Button)
                       and w.cget('text') == 'My external drive is slow or failing')
            nav.invoke()
            options = [str(x) for w in widgets if isinstance(w, ttk.Combobox)
                       for x in w.cget('values')]
            self.assertTrue(any('Balanced: bounded error recovery' in x for x in options))
        self.open_app(scenario)

    def test_image_scan_updates_actual_bytes_read_speed_and_eta(self):
        from driverepair_desktop import gui, devices
        original_tk = tk.Tk
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'patient.img'
            src.write_bytes(b'Q' * (2 * 1024 * 1024))
            errors = []
            verified = [False]
            def patched_tk(*args, **kwargs):
                root = original_tk(*args, **kwargs)
                root.report_callback_exception = lambda *e: errors.append(str(e[1]))
                def begin():
                    try:
                        widgets = list(all_widgets(root))
                        navigate = next(w for w in widgets if isinstance(w, ttk.Button)
                                        and w.cget('text') == 'I need a forensic working copy')
                        navigate.invoke()
                        notebook = next(w for w in widgets if isinstance(w, ttk.Notebook))
                        tab = root.nametowidget(notebook.select())
                        entries = [w for w in all_widgets(tab) if isinstance(w, ttk.Entry)]
                        entries[0].insert(0, str(src))
                        scan = next(w for w in all_widgets(tab) if isinstance(w, ttk.Button)
                                    and w.cget('text') == 'Scan')
                        scan.invoke()
                        start_button = next(w for w in all_widgets(root)
                                            if isinstance(w, ttk.Button) and w.cget('text') == 'Start job')
                        self.assertEqual(str(start_button.cget('state')), 'normal')
                        start_button.invoke()
                    except Exception as exc:
                        errors.append(f'begin: {exc}')
                        close_window(root)
                        return
                    root.after(300, lambda: check(time.monotonic()+8))
                def check(deadline):
                    if time.monotonic() > deadline:
                        errors.append('Timed out waiting for scan metric telemetry')
                        close_window(root)
                        return
                    labels = list(all_widgets(root))
                    try:
                        read_label = next(w for w in labels if isinstance(w, tk.Label)
                                          and w.cget('text') == 'BYTES READ')
                        # Four summary panels have stable order.
                        row = read_label.master.master
                        stats = [w for w in row.winfo_children() if isinstance(w, tk.Frame)]
                        values = []
                        for card in stats:
                            varlabel = [w for w in card.winfo_children() if isinstance(w, tk.Label)]
                            if len(varlabel) >= 2:
                                values.append(root.getvar(varlabel[1].cget('textvariable')))
                        if (len(values) >= 4 and 'MiB' in str(values[0]) and
                                str(values[2]) not in {'—', 'Measuring…'} and
                                str(values[3]) not in {'—', 'Calculating…'}):
                            verified[0] = True
                            close_window(root)
                            return
                    except (StopIteration, tk.TclError):
                        pass
                    root.after(100, lambda: check(deadline))
                root.after(350, begin)
                return root
            with mock.patch.object(tk, 'Tk', side_effect=patched_tk), \
                 mock.patch.object(devices, 'list_external_devices', return_value=[]), \
                 mock.patch.object(messagebox, 'askyesno', return_value=True), \
                 mock.patch.object(messagebox, 'showerror', side_effect=lambda *a,**kw: errors.append(str(a))):
                gui.launch()
            self.assertFalse(errors, errors)
            self.assertTrue(verified[0])

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
                        start_button = next(w for w in all_widgets(root)
                                            if isinstance(w, ttk.Button) and w.cget('text') == 'Start job')
                        self.assertEqual(str(start_button.cget('state')), 'normal')
                        self.assertFalse(dst.exists(), 'Choosing Rescue must not start disk I/O')
                        start_button.invoke()
                    except Exception as exc:
                        errors.append(str(exc))
                        close_window(root)
                        return
                    check(time.monotonic()+12)
                def check(deadline):
                    if errors or time.monotonic() > deadline:
                        errors.append('Rescue did not complete in time' if not errors else '')
                        close_window(root)
                        return
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
                 mock.patch.object(messagebox, 'askyesno', return_value=True), \
                 mock.patch.object(messagebox,'showerror',side_effect=lambda a,b,**kw: errors.append(f'{a}: {b}')):
                gui.launch()
            self.assertFalse(errors, errors)
            self.assertTrue(completed[0], 'GUI rescue did not produce byte-identical output')


if __name__ == '__main__':
    unittest.main()
