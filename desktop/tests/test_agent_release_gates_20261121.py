"""No hardware is accessed; pin the release and evidence mechanisms."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseHygieneTests(unittest.TestCase):
    def test_repo_current_version_passes(self):
        result = tool('check_release_hygiene').check_repository(ROOT)
        self.assertEqual(result['errors'], [])

    def test_mismatched_status_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p/'desktop').mkdir()
            (p/'docs').mkdir()
            (p/'desktop/pyproject.toml').write_text('[project]\nversion = "0.3.3b35"\n', encoding='utf-8')
            (p/'status.md').write_text('**0.3.3b34** outdated', encoding='utf-8')
            (p/'docs/RELEASE_STATUS.md').write_text('# DriveRepair release status — v0.3.3b35\n', encoding='utf-8')
            (p/'README.md').write_text('Run `dist/DriveRepair-0.3.3b35-public-beta.pyz`', encoding='utf-8')
            result = tool('check_release_hygiene').check_repository(p)
            self.assertTrue(any('status.md' in err for err in result['errors']))

    def test_readme_examples_cannot_use_stale_version(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p/'desktop').mkdir()
            (p/'docs').mkdir()
            (p/'desktop/pyproject.toml').write_text('[project]\nversion = "0.3.3b35"\n', encoding='utf-8')
            (p/'status.md').write_text('**0.3.3b35** testing', encoding='utf-8')
            (p/'docs/RELEASE_STATUS.md').write_text('# DriveRepair release status — v0.3.3b35\n', encoding='utf-8')
            (p/'README.md').write_text('Run `dist/DriveRepair-0.3.3b31-public-beta.pyz`', encoding='utf-8')
            result = tool('check_release_hygiene').check_repository(p)
            self.assertTrue(any('README.md' in err for err in result['errors']))


class PromotionEvidenceTests(unittest.TestCase):
    def test_missing_independent_evidence_never_passes(self):
        gate = tool('check_release_readiness')
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp)/'image.iso'
            artifact.write_bytes(b'not a real iso')
            evidence = Path(temp)/'evidence.json'
            evidence.write_text(json.dumps({'version':'0.3.3b35','source_commit':'f00dbabe'*5,
                    'artifact_sha256':'bad', 'checks':{'bios_vm':'PASS'}}), encoding='utf-8')
            result = gate.evaluate(evidence, artifact, '0.3.3b35', 'f00dbabe'*5)
            self.assertFalse(result['ready'])
            self.assertIn('artifact_sha256 mismatch', result['failures'])
            self.assertTrue(any('uefi_vm' in x for x in result['failures']))

    def test_commit_identifier_must_be_full_sha(self):
        gate = tool('check_release_readiness')
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp)/'image.iso'
            artifact.write_bytes(b'test')
            evidence = Path(temp)/'evidence.json'
            evidence.write_text(json.dumps({'version':'0.3.3b35','source_commit':'short',
                'artifact_sha256':gate.file_sha256(artifact),
                'checks':{key:{'status':'PASS','evidence':'manual record'} for key in gate.REQUIRED}}), encoding='utf-8')
            result = gate.evaluate(evidence, artifact, '0.3.3b35', 'short')
            self.assertFalse(result['ready'])

    def test_all_evidence_bound_to_same_artifact_passes_logic_only(self):
        import hashlib
        gate = tool('check_release_readiness')
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp)/'image.iso'
            artifact.write_bytes(b'example bytes not a bootable iso')
            evidence = Path(temp)/'evidence.json'
            data = {'version':'0.3.3b35','source_commit':'f00dbabe'*5,
                    'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    'checks':{key:{'status':'PASS','evidence':'documented testing record'}
                              for key in gate.REQUIRED}}
            evidence.write_text(json.dumps(data), encoding='utf-8')
            result = gate.evaluate(evidence, artifact, '0.3.3b35', 'f00dbabe'*5)
            self.assertTrue(result['ready'])
            self.assertEqual(result['failures'], [])


class BootSmokeTests(unittest.TestCase):
    def test_bios_vm_uses_only_readonly_iso(self):
        smoke = tool('smoke_live_iso')
        args = smoke.make_qemu_command('bios','/tmp/DriveRepair.iso','/tmp/serial.log')
        self.assertIn('-cdrom',args)
        self.assertNotIn('-hda',args)
        self.assertNotIn('-hdb',args)
        self.assertNotIn('-drive',args)
        self.assertNotIn('-enable-kvm',args)

    def test_uefi_vm_uses_readonly_firmware_and_disposable_vars(self):
        smoke = tool('smoke_live_iso')
        args = smoke.make_qemu_command('uefi','/tmp/DriveRepair.iso','/tmp/serial.log',
                  ovmf_code='/boot/OVMF_CODE.fd', ovmf_vars='/tmp/OVMF_VARS.fd')
        self.assertIn('if=pflash,format=raw,unit=0,readonly=on,file=/boot/OVMF_CODE.fd',args)
        self.assertIn('if=pflash,format=raw,unit=1,file=/tmp/OVMF_VARS.fd',args)
        self.assertIn('-cdrom',args)

    def test_bundled_live_recipes_match_checkout(self):
        for name in ('build_live_iso.sh', 'check_live_iso.sh'):
            self.assertEqual((ROOT/'scripts'/name).read_bytes(),
                             (ROOT/'desktop/driverepair_desktop/boot_resources'/name).read_bytes())

    def test_both_menus_and_live_marker_configured(self):
        text=(ROOT/'scripts/build_live_iso.sh').read_text(encoding='utf-8')
        self.assertIn('config/bootloaders/grub-efi/grub.cfg',text)
        self.assertIn('driverepair-vm-boot-check.service',text)
        self.assertIn('config/includes.chroot/etc/systemd/system',text)


class SmartProbeTests(unittest.TestCase):
    def test_valid_windows_alias_only(self):
        q = tool('qa_smart_probe')
        self.assertEqual(q.windows_alias('windows:PhysicalDrive2'),'/dev/pd2')
        with self.assertRaises(ValueError):
            q.windows_alias('windows:PhysicalDrive2 && erase')

    def test_empty_json_is_not_a_successful_smart_probe(self):
        q = tool('qa_smart_probe')
        class Result:
            returncode = 0
            stdout = b'{"smartctl":{"exit_status":0}}'
            stderr = b''
        report = q.probe('windows:PhysicalDrive2', run=lambda *a, **kw: Result())
        self.assertEqual(report['status'], 'UNVERIFIED')

    def test_error_output_does_not_leak_serials(self):
        q = tool('qa_smart_probe')
        # Probe report contains only derived fields, never raw stdout.
        class Result:
            returncode=2
            stdout=b'{"serial_number":"CONFIDENTIAL","smartctl":{"exit_status":2},"device":{"protocol":"SCSI"}}'
            stderr=b'raw identifying data HERE'
        calls=[]
        def fake_run(args, **kw):
            calls.append(args)
            return Result()
        report = q.probe('windows:PhysicalDrive2', executable='smartctl', run=fake_run)
        self.assertEqual(report['status'],'UNVERIFIED')
        self.assertNotIn('CONFIDENTIAL',json.dumps(report))
        self.assertNotIn('raw identifying data HERE',json.dumps(report))
        self.assertEqual(calls[0][-1],'/dev/pd2')


class ConfidenceTests(unittest.TestCase):
    def test_uncalibrated_187_with_zero_other_ata_attributes_is_not_100(self):
        from driverepair_desktop.reliability_score import assess
        snap={'smart_status_passed': True, 'ata_selected_raw_attributes': [
            {'id':5, 'raw_value':0}, {'id':187,'raw_value':65535},
            {'id':197, 'raw_value':0}, {'id':198, 'raw_value':0}]}
        result=assess(snap)
        self.assertIsNone(result['score'])
        self.assertIn('unscored', ' '.join(result['reasons']))

    def test_uninterpreted_vendor_raw_187_cannot_claim_precise_82_score(self):
        from driverepair_desktop.reliability_score import assess
        snap={'smart_status_passed': True, 'ata_selected_raw_attributes': [
            {'id':187, 'raw_value':65535}]}
        result=assess(snap)
        self.assertIsNone(result['score'])
        self.assertIn('vendor', ' '.join(result['reasons']).lower())


if __name__ == '__main__':
    unittest.main()
