import unittest
from driverepair_desktop.device_tools import device_tool_args

class DeviceToolsTests(unittest.TestCase):
    def test_readonly_firmware_and_inspect(self):
        for name in ('firmware-info','inspect-storage'):
            args=device_tool_args(name,device_id='windows:PhysicalDrive9')
            self.assertNotIn('--execute',args)
            self.assertNotIn('--ack-destructive',args)
    def test_benchmark_is_stress_aware(self):
        with self.assertRaises(PermissionError):
            device_tool_args('benchmark-external',device_id='disk')
        args=device_tool_args('benchmark-external',device_id='disk',read_risk_approved=True)
        self.assertIn('--ack-risk',args)
    def test_failed_region_requires_fingerprint_and_offset(self):
        with self.assertRaises(ValueError):
            device_tool_args('probe-region',device_id='disk',offset=7,read_risk_approved=True)
        args=device_tool_args('probe-region',device_id='disk',offset=4096,
                              fingerprint='123456789abc',read_risk_approved=True)
        self.assertIn('--confirm-identity',args)
        self.assertNotIn('--ack-destructive',args)
    def test_os_optimization_is_advice_only(self):
        args=device_tool_args('optimize-volume',device_id='disk',volume_letter='E')
        self.assertNotIn('--execute',args)
    def test_unknown_operation_refused(self):
        with self.assertRaises(ValueError):
            device_tool_args('refresh-external',device_id='disk')

if __name__=='__main__':unittest.main()
