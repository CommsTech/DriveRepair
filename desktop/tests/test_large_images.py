import json
import os
import tempfile
import sys
import unittest
from pathlib import Path

from driverepair_desktop.recovery import rescue_reader

class LargeImagesTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith("linux"), "12 TB sparse-file test requires Linux")
    def test_twelve_tb_rescue_does_not_materialize_work_list(self):
        # Sparse file: logical size 12TB, *physical* usage only one tiny block.
        class Reader:
            def read_at(self, offset, count):
                if offset != 0:
                    raise AssertionError('Unexpected large scan')
                return b'Q' * count
        with tempfile.TemporaryDirectory() as root:
            output = os.path.join(root, 'sparse.img')
            state = rescue_reader(Reader(), size=12_000_000_000_000, sector=512,
                                  output=output, source_token='mock-12TB',
                                  chunk=4096, max_chunks=1)
            self.assertEqual(state['cursor'], 4096)
            self.assertEqual(os.stat(output).st_size, 12_000_000_000_000)
            self.assertLess(os.stat(output).st_blocks * 512, 64 * 1024 * 1024)
            self.assertEqual(Path(output).open('rb').read(4096), b'Q' * 4096)
            self.assertEqual(json.loads(Path(output + '.rescue.json').read_text())['cursor'],4096)

if __name__ == '__main__':
    unittest.main()
