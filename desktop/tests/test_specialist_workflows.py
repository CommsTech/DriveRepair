"""No raw device I/O: Qt advanced toolbox command contract and write isolation."""
import tempfile
from pathlib import Path
import unittest

from driverepair_desktop.advanced_workflows import ACTIONS, build_specialist_command

class SpecialistWorkflowsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.image=self.root/'original.img'
        self.image.write_bytes(b'FS_IMAGE')
    def action(self,command):
        return next(x for x in ACTIONS if x.command==command)
    def test_specialist_tools_cover_old_tk_recovery_roles(self):
        names={x.command for x in ACTIONS}
        self.assertTrue({'scan-image','detect-filesystems','recover-image','undelete-fat32',
            'list-deleted-fat32','recover-selected-tsk','carve-image','integrity-baseline',
            'integrity-audit','integrity-restore-copy','check-ext-image',
            'repair-ext-image','salvage-zip','verify-images','rescue-image'} <= names)
        self.assertFalse(any(x.command in {'refresh-external','care-external'} for x in ACTIONS))
    def test_inspection_does_not_grant_destructive_flags(self):
        args=build_specialist_command(self.action('detect-filesystems'),source=str(self.image))
        self.assertEqual(args,['detect-filesystems','--image',str(self.image),'--json'])
    def test_new_output_cannot_overlap_source_or_existing(self):
        with self.assertRaisesRegex(ValueError,'must not equal'):
            build_specialist_command(self.action('carve-image'),source=str(self.image),output=str(self.image))
        existing=self.root/'existing'
        existing.mkdir()
        with self.assertRaisesRegex(FileExistsError,'NEW output'):
            build_specialist_command(self.action('carve-image'),source=str(self.image),output=str(existing))
    def test_selected_file_recovery_only_uses_explicit_ids(self):
        action=self.action('recover-selected-tsk')
        with self.assertRaisesRegex(ValueError,'file IDs'):
            build_specialist_command(action,source=str(self.image),output=str(self.root/'recovered'))
        args=build_specialist_command(action,source=str(self.image),output=str(self.root/'recovered'),
                                      file_ids='15,21')
        self.assertEqual(args.count('--file-id'),2)
    def test_copy_repair_requires_separate_user_approval(self):
        action=self.action('repair-ext-image')
        with self.assertRaises(PermissionError):
            build_specialist_command(action,source=str(self.image),output=str(self.root/'clone'))
        args=build_specialist_command(action,source=str(self.image),output=str(self.root/'clone'),
                                      clone_approved=True)
        self.assertIn('--ack-repair',args)
    def test_integrity_restoration_requires_independent_snapshot(self):
        action=self.action('integrity-restore-copy')
        manifest=self.root/'manifest.json'
        manifest.write_text('{}')
        with self.assertRaisesRegex(ValueError,'independent'):
            build_specialist_command(action,source=str(self.image),output=str(self.root/'clean'),
                reference=str(self.image),manifest=str(manifest),clone_approved=True)

if __name__=='__main__':
    unittest.main()
