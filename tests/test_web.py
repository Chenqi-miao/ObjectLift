import tempfile
import unittest
from pathlib import Path
from PIL import Image
from ui.page import build_page


class WebTests(unittest.TestCase):
    def test_callbacks_clear_stale_results_on_failure_and_new_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            demo = build_page(Path(directory) / 'jobs')
            callbacks = {fn.fn.__name__: fn.fn for fn in demo.fns.values()}
            image = Path(directory) / 'source.png'
            Image.new('RGBA', (40, 30), (10, 20, 30, 128)).save(image)
            result = callbacks['on_upload'](str(image))
            self.assertEqual(result[4:6], [40, 30])
            self.assertEqual(result[6:13], [None] * 7)
            cropped = callbacks['do_crop'](result[0], 0, 0, 20, 20, 0)
            self.assertTrue(Path(cropped[1]).is_file())
            self.assertEqual(cropped[3:7], [None] * 4)
            invalid = callbacks['do_crop'](result[0], 20, 0, 1, 20, 0)
            self.assertEqual(invalid[:7], [None] * 7)
            cleared = callbacks['on_upload'](None)
            self.assertIsNone(cleared[0])
            self.assertEqual(cleared[6:13], [None] * 7)
