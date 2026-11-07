import tempfile
import unittest
from pathlib import Path

import gradio as gr
from PIL import Image

from services.library import Library
from ui.library_page import build_page


class Encoder:
    model_id = 'test-only'
    revision = 'v1'

    def image(self, path):
        return [1, 0]

    def text(self, query):
        return [1, 0]


class LibraryPageTests(unittest.TestCase):
    def test_filters_search_selection_and_empty_search(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = Library(root / 'data')
            page = build_page(library, Encoder())
            callbacks = {fn.fn.__name__: fn.fn for fn in page.fns.values()}
            for name, color in [('Apple.png', 'red'), ('100%.png', 'blue')]:
                path = root / name
                Image.new('RGB', (20, 10), color).save(path)
                library.import_image(path)
            self.assertEqual(len(library.list_assets(keyword='%')), 1)
            gallery, assets, summary = callbacks['refresh']('apple', 'pending')
            self.assertEqual(len(assets), 1)
            self.assertEqual(assets[0]['original_name'], 'Apple.png')
            list(callbacks['index']('', '全部'))
            self.assertEqual(library.statistics()['searchable'], 2)
            self.assertEqual(library.list_assets(status='pending'), [])
            results, scores, message, hits = callbacks['search']('图片', 1)
            self.assertEqual(len(hits), 1)
            detail, download, player = callbacks['select'](
                hits, gr.SelectData(None, {'index': 0, 'value': None}))
            self.assertTrue(Path(download).is_file())
            self.assertIn(scores[0][1], detail)
            empty = callbacks['search'](' ', 10)
            self.assertEqual(empty[0], [])
            self.assertEqual(empty[3], [])
