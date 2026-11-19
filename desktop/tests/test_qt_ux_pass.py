"""Offscreen Qt checks for the UX pass: no drives, no disks, no patient I/O.

These run when PySide6 is installed (release hosts); elsewhere they skip the
same way the existing Qt smoke test does.
"""
from __future__ import annotations

import os
import time
import unittest

try:
    import PySide6  # noqa: F401
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed; run on a release host')
class WorkstationUxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ['DRIVEREPAIR_QT_SMOKE'] = '1'
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QLineEdit, QComboBox

        from driverepair_desktop.qtgui import launch

        cls.qapp = QApplication.instance() or QApplication([])
        QTimer.singleShot(600, cls.qapp.quit)
        launch()
        windows = [w for w in cls.qapp.topLevelWidgets() if w.isWindow()]
        if not windows:
            raise unittest.SkipTest('Workstation window unavailable in this environment')
        cls.win = max(windows, key=lambda w: w.width() * w.height())
        cls.win.resize(1440, 900)
        cls.qapp.processEvents()
        cls.QComboBox = QComboBox
        cls.QLineEdit = QLineEdit

    def test_evidence_tabs_are_readable_not_clipped(self):
        tabs = self.win.evidence_tabs
        self.assertEqual(tabs.count(), 2)
        for index in range(tabs.count()):
            text = tabs.tabText(index)
            rect = tabs.tabBar().tabRect(index)
            needed = tabs.tabBar().fontMetrics().horizontalAdvance(text)
            self.assertGreaterEqual(rect.width(), needed,
                                    f'tab {text!r} ({rect.width()}px) clips {needed}px of text')
        self.assertIn('throughput', tabs.tabToolTip(1).lower())

    def test_disabled_primary_action_does_not_look_actionable(self):
        button = self.win.start
        if button.isEnabled():
            self.skipTest('A drive is selected on this host; disabled styling not observable')
        image = button.grab().toImage()
        samples = [image.pixelColor(x, y) for x in range(4, image.width(), 12)
                   for y in range(4, image.height(), 8)]
        accent_like = [c for c in samples
                       if c.green() > 110 and c.green() > c.red() + 30]
        self.assertLess(len(accent_like), len(samples) * 0.05,
                        'disabled Start still renders with the teal action colour')

    def test_empty_inventory_disables_the_selector_and_explains(self):
        self.win._devices = []
        self.win.update_action_state()
        self.assertFalse(self.win.device_box.isEnabled())
        self.assertTrue(self.win.device_box.placeholderText())

    def test_core_controls_expose_accessible_names(self):
        for widget in (self.win.device_box, self.win.job_box, self.win.dest):
            self.assertTrue(widget.accessibleName().strip(),
                            f'{type(widget).__name__} has no accessible name')

    def test_sidebar_support_button_text_fits(self):
        from PySide6.QtWidgets import QPushButton
        button = next(b for b in self.win.findChildren(QPushButton)
                      if b.objectName() == 'sponsor')
        needed = button.fontMetrics().horizontalAdvance(button.text())
        self.assertGreaterEqual(button.contentsRect().width() - 16, needed,
                                'Support button text is clipped by the sidebar width')
        self.assertIn('Sponsor', button.toolTip())

    def test_keyboard_start_is_gated_like_the_button(self):
        self.assertEqual(self.win.start_shortcut.key().toString(), 'Ctrl+Return')
        self.assertEqual(self.win.start_shortcut.isEnabled(), self.win.start.isEnabled())

    def test_progress_events_are_coalesced_then_flushed(self):
        self.assertTrue(hasattr(self.win, '_render_timer'))
        self.assertLessEqual(self.win._render_timer.interval(), 200)
        # A phase change always renders; establish SCANNING first.
        self.win.progress_event({'phase': 'SCANNING', 'attempted_bytes': 1024,
                                 'probe_index': 1, 'probe_total': 100})
        self.assertEqual(self.win._last_phase, 'SCANNING')
        self.assertIsNone(self.win._pending_render)
        self.win._last_render_at = time.monotonic()
        self.win._pending_render = None
        self.win.progress_event({'phase': 'SCANNING', 'attempted_bytes': 2048,
                                 'probe_index': 2, 'probe_total': 100})
        self.assertIsNotNone(self.win._pending_render,
                             'in-phase event should wait for the next frame')
        self.win._flush_progress_render()
        self.assertIsNone(self.win._pending_render)


if __name__ == '__main__':
    unittest.main()
