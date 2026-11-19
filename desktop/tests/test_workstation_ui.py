"""No Qt or physical disks needed; presentation must not overclaim media health."""
import unittest
from driverepair_desktop.workstation_ui import (
    WORKSPACES, can_start, operation_impact, operation_family, operator_summary,
    should_render_progress,
)


class WorkstationPresentationTests(unittest.TestCase):
    def test_workspaces_and_risk_copy(self):
        self.assertEqual({operation_family(k) for k in ('scanquick', 'rescue', 'carequick')},
                         {'check', 'recover', 'fix'})
        self.assertIn('Experimental', WORKSPACES['fix'].operation)
        self.assertIn('READ-ONLY', operation_impact('rescue')[0])
        self.assertIn('EXPERIMENTAL', operation_impact('carequick')[0])

    def test_no_drive_is_not_a_ready_operation(self):
        enabled, instruction = can_start('scanquick', device_selected=False,
                                         image_exists=False, running=False, public_beta=True)
        self.assertFalse(enabled)
        self.assertIn('external source drive', instruction)

    def test_image_recovery_does_not_require_external_drive(self):
        enabled, _ = can_start('rescueimage', device_selected=False,
                                image_exists=True, running=False, public_beta=True)
        self.assertTrue(enabled)
        enabled, _ = can_start('rescueimage', device_selected=True,
                                image_exists=False, running=False, public_beta=True)
        self.assertFalse(enabled)

    def test_engineering_repair_requires_idle_and_non_beta(self):
        self.assertFalse(can_start('carefull', device_selected=True, image_exists=False,
                                  running=False, public_beta=True)[0])
        self.assertFalse(can_start('carefull', device_selected=True, image_exists=False,
                                  running=True, public_beta=False)[0])
        self.assertTrue(can_start('carefull', device_selected=True, image_exists=False,
                                 running=False, public_beta=False)[0])

    def test_summary_labels_coverage_and_avoids_false_certification(self):
        text = operator_summary(operation='Quick check',
            device={'model':'Example Drive','bus':'usb','serial_suffix':'1234'},
            result='Scan completed', explanation='Read-only.', progress='100%',
            errors='2', observed_coverage='10.0%')
        self.assertIn('Measured successful read coverage: 10.0%', text)
        self.assertIn('Failed read requests (not confirmed bad sectors): 2', text)
        self.assertIn('do not certify', text)
        self.assertNotIn('100% healthy', text)


class ProgressCadenceTests(unittest.TestCase):
    """Fast media must not flood the UI thread with thousands of repaints."""

    def test_first_event_always_renders(self):
        self.assertTrue(should_render_progress(now=5.0, last_render_at=None,
                                               phase='SCANNING', last_phase=None))

    def test_rapid_in_phase_events_are_coalesced(self):
        self.assertFalse(should_render_progress(now=1.02, last_render_at=1.0,
                                                phase='SCANNING', last_phase='SCANNING'))

    def test_render_resumes_after_the_interval(self):
        self.assertTrue(should_render_progress(now=1.1, last_render_at=1.0,
                                               phase='SCANNING', last_phase='SCANNING'))

    def test_phase_change_renders_immediately(self):
        self.assertTrue(should_render_progress(now=1.01, last_render_at=1.0,
                                               phase='REFRESH', last_phase='SCANNING'))

    def test_terminal_event_renders_immediately(self):
        self.assertTrue(should_render_progress(now=1.001, last_render_at=1.0,
                                               phase='SCANNING', last_phase='SCANNING',
                                               terminal=True))


if __name__ == '__main__':
    unittest.main()
