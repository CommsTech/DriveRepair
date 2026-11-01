import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from test_fat32_undelete import fat32_image
from driverepair_desktop.cli import run


class CatalogCliIntegration(unittest.TestCase):
    def test_preview_then_selected_restore(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'source.img'
            payload = fat32_image(src)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = run(['list-deleted-fat32', '--image', str(src), '--json'])
            self.assertEqual(code, 0)
            entries = json.loads(out.getvalue())['candidates']
            self.assertEqual(len(entries), 1)
            output_dir = Path(td) / 'selected'
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = run(['undelete-fat32', '--image', str(src), '--output-dir', str(output_dir),
                            '--file-id', entries[0]['id'], '--json'])
            self.assertEqual(code, 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result['files_recovered'], 1)
            self.assertEqual((output_dir / result['files'][0]['filename']).read_bytes(), payload)

if __name__ == '__main__':
    unittest.main()
