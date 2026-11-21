"""Real PySide6 widgets, synthetic device records; NEVER open a physical disk.

Run on a Windows desktop or an offscreen Qt test host. The application is told
not to run its startup device discovery, and all synthetic IDs are impossible
Windows physical-drive paths.
"""
from __future__ import annotations

import os
import unittest

try:
    import PySide6  # noqa: F401
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed on this host')
class NativeQtRepairRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DRIVEREPAIR_QT_TEST_NO_DEVICES'] = '1'
        os.environ['DRIVEREPAIR_QT_SMOKE'] = '1'
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from driverepair_desktop.qtgui import launch
        cls.app = QApplication.instance() or QApplication([])
        QTimer.singleShot(450, cls.app.quit)
        launch()
        windows = [w for w in cls.app.topLevelWidgets() if w.isWindow() and
                   hasattr(w, 'device_box') and hasattr(w, 'job_box')]
        if not windows:
            # With PySide6 installed (this class already skipped when absent), a
            # missing workstation is a hard failure — never a green skip.
            raise AssertionError('DriveRepair Qt main window unavailable with PySide6 installed')
        cls.win = windows[0]

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'win'):
            cls.win.close()
            cls.app.processEvents()

    def setUp(self):
        self.win.device_box.clear()
        self.win._devices = []
        self.win._health_by_device.clear()
        self.win._auto_probe_attempted.clear()
        self.win._auto_probe_timer.stop()

    def synthetic(self, model, key, snap):
        device = {'id': f'SYNTHETIC-NOT-A-DRIVE-{key}', 'model': model,
                  'bus': 'usb', 'sector_size': 512, 'size_bytes': 1000000000,
                  'serial_suffix': '0001', 'identity_hint': key}
        self.win._devices = [device]
        self.win._health_by_device[key] = snap
        self.win._auto_probe_attempted.add(key)
        self.win.device_box.addItem(model, device)
        # QComboBox can stay at index -1 after clear()+addItem; force selection.
        self.win.device_box.setCurrentIndex(0)
        self.win._auto_probe_timer.stop()
        return device

    def test_ssd_blocks_hdd_method_without_switching_to_chkdsk(self):
        from driverepair_desktop.repair_routes import choose_repair_route
        self.synthetic('SanDisk SSD 500GB', 'fake-ssd', {'reported_medium': 'ssd'})
        self.win.select_goal('carequick')
        self.win.update_action_state()
        self.assertEqual(self.win.job_box.currentData(), 'carequick')
        self.assertFalse(self.win.start.isEnabled())
        self.assertIn('filesystem repair above', self.win.start.text())
        self.assertFalse(self.win.start_shortcut.isEnabled())
        self.assertIsNone(self.win.proc)
        route = choose_repair_route(self.win.selected(),
                                    self.win._health_by_device.get('fake-ssd'))
        self.assertEqual(route.action, 'filesystem')
        self.assertFalse(route.hdd_region_write_candidate)

    def test_ssd_operator_can_explicitly_select_windows_filesystem_repair(self):
        from unittest.mock import patch
        self.synthetic('SanDisk SSD 500GB', 'fake-ssd', {'reported_medium':'ssd'})
        self.win.select_goal('carequick')
        with patch('driverepair_desktop.qtgui.sys.platform', 'win32'):
            self.win.resolve_repair_next()
        self.assertEqual(self.win.job_box.currentData(), 'winfsrepair')
        self.assertIsNone(self.win.proc)  # selection never runs CHKDSK

    def test_hdd_ui_review_does_not_begin_a_write(self):
        from driverepair_desktop.repair_routes import choose_repair_route
        self.synthetic('ST1000LM048', 'fake-hdd', {
            'status':'smart_passed_limited', 'smart_status_passed': True,
            'reported_medium':'hdd', 'rotation_rate_rpm':5400,
            'device_protocol':'ATA'})
        self.win.select_goal('carequick')
        self.win.update_action_state()
        self.assertEqual(self.win.job_box.currentData(), 'carequick')
        self.assertIn('HDD', self.win.start.text())
        self.assertIsNone(self.win.proc)
        route = choose_repair_route(self.win.selected(),
                                    self.win._health_by_device.get('fake-hdd'))
        self.assertEqual(route.action, 'review')
        self.assertTrue(route.hdd_region_write_candidate)
        # Review CTA must not spawn a modifying worker by itself.
        self.assertIsNone(self.win.proc)

    def test_chkdsk_is_never_selected_implicitly(self):
        self.synthetic('SanDisk SSD 500GB', 'fake-ssd', {'reported_medium':'ssd'})
        self.win.select_goal('carequick')
        self.win.update_action_state()
        self.assertNotEqual(self.win.job_box.currentData(), 'winfsrepair')
        self.assertIsNone(self.win.proc)


if __name__ == '__main__':
    unittest.main()
