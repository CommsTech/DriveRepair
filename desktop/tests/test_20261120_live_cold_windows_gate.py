"""Source-based regression contracts: no disk/USB writes are performed."""
from pathlib import Path
import tempfile
import unittest
import zipfile

from driverepair_desktop.boot_media import export_build_kit
from driverepair_desktop.cold_storage import create_baseline
from driverepair_desktop.health import _smartctl_low_bits_message, smartctl_device_path
from driverepair_desktop.devices import Device
from driverepair_desktop.repair_routes import choose_repair_route

ROOT = Path(__file__).resolve().parents[2]

class LiveAndRoutingContracts(unittest.TestCase):
    def test_iso_branded_menu_and_boot_args_are_in_both_kits(self):
        grub = (ROOT/'scripts/driverepair-grub.cfg').read_text(encoding='utf-8')
        self.assertIn('Start recovery workstation',grub)
        self.assertIn('Compatibility graphics',grub)
        self.assertIn('nomodeset',grub)
        self.assertIn('@KERNEL_LIVE@',grub)
        self.assertIn('@INITRD_LIVE@',grub)
        for source in ('scripts/build_live_iso.sh', 'desktop/driverepair_desktop/boot_resources/build_live_iso.sh'):
            recipe=(ROOT/source).read_text(encoding='utf-8')
            self.assertIn('live-config.username=driverepair', recipe)
            self.assertIn('autologin-user=driverepair',recipe)
            self.assertIn('config/bootloaders/grub-pc/grub.cfg',recipe)
            self.assertIn('config/includes.chroot/etc/xdg/autostart/driverepair.desktop',recipe)
        self.assertIn('DriveRepair - Compatibility graphics',
                      (ROOT/'scripts/check_live_iso.sh').read_text(encoding='utf-8'))

    def test_wsl_standalone_kit_contains_menu_and_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            for repo in (ROOT, None):
                target=Path(tmp)/('from-checkout.zip' if repo else 'from-portable.zip')
                export_build_kit(repo,target)
                with zipfile.ZipFile(target) as z:
                    self.assertIn('driverepair/scripts/driverepair-grub.cfg',z.namelist())
                    self.assertIn('driverepair/docs/DRIVEREPAIR_LIVE_START_HERE.txt',z.namelist())

    def test_hdd_repair_never_implicitly_routes_to_chkdsk(self):
        code=(ROOT/'desktop/driverepair_desktop/qtgui.py').read_text(encoding='utf-8')
        resolving=code.split('def resolve_repair_next(self):',1)[1].split('def update_drive_profile(',1)[0]
        self.assertNotIn('self.start_windows_filesystem_repair()',resolving)
        self.assertNotIn("self.job_box.setCurrentIndex(index)",
                         code.split('def select_goal(self, goal):',1)[1].split('def update_action_state(',1)[0])
        self.assertIn("route.action == 'review'",code)
        profile={'model':'ST1000LM048','bus':'usb','serial_suffix':'***0001','sector_size':512}
        snap={'status':'smart_passed_limited','reported_medium':'hdd','rotation_rate_rpm':5400}
        self.assertEqual(choose_repair_route(profile,snap).action,'review')

    def test_command_line_parse_error_not_confused_with_unavailable_bridge(self):
        self.assertIn('NOT evidence that the USB bridge lacks SMART', _smartctl_low_bits_message(1))
        self.assertIn('dock/cable', _smartctl_low_bits_message(2))

    def test_win32_smartctl_uses_documented_readonly_pd_alias(self):
        disk=Device('windows:PhysicalDrive2',r'\\.\PhysicalDrive2',
                    'ST1000LM048',1024*1024,512,'usb','example123')
        self.assertEqual(smartctl_device_path(disk), '/dev/pd2')
        mismatched=Device('windows:PhysicalDrive3',disk.path,
                          disk.model,disk.size_bytes,disk.sector_size,disk.bus,disk.serial)
        with self.assertRaisesRegex(RuntimeError,'identity/path mismatch'):
            smartctl_device_path(mismatched)

    def test_baseline_provides_determinate_file_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'photos'
            root.mkdir()
            for i in range(27):
                (root/f'{i}.jpg').write_bytes(bytes([i]))
            seen=[]
            result=create_baseline(str(root),str(Path(tmp)/'baseline.json'),progress=seen.append)
            self.assertEqual(result['files_baselined'],27)
            self.assertEqual(seen[-1]['files_total'],27)
            self.assertEqual(seen[-1]['files_processed'],27)

if __name__ == '__main__':
    unittest.main()
