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
    def test_tag_diagnostics_include_unindexed_and_missing_images(self):
        from services.captions import CaptionService
        from types import SimpleNamespace
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = Library(root / 'data')
            ids = []
            for color in ['red', 'blue', 'green']:
                path = root / f'{color}.png'
                Image.new('RGB', (20, 20), color).save(path)
                ids.append(library.import_image(path)['asset_id'])
            service = CaptionService(library, SimpleNamespace())
            service.save(ids[0], 'ready', '自然画面', 'test', tags=['自然'])
            service.save(ids[1], 'ready', '无标签', 'test', tags=[])
            page = build_page(library, Encoder())
            callbacks = page.objectlift_callbacks
            all_rows = callbacks['inspect_tags']('全部图片')
            self.assertEqual(len(all_rows[4]), 3)
            natural = callbacks['inspect_tags']('自然')
            self.assertEqual(len(natural[4]), 1)
            self.assertEqual(next(r for r in natural[1] if r[0] == '自然'), ['自然', 1, 0])
            self.assertEqual(len(callbacks['inspect_tags']('未生成')[4]), 1)
            self.assertEqual(len(callbacks['inspect_tags']('已完成但无标签')[4]), 1)
            self.assertEqual(len(callbacks['inspect_tags']('未分类')[4]), 1)
            self.assertEqual(callbacks['inspect_tags']('动物')[4], [])
            self.assertEqual(len(callbacks['browse']('', '全部', '全部', '', 20)[1]), 3)
            self.assertEqual(len(callbacks['browse']('', '图片', '自然', '', 20)[1]), 1)
            self.assertEqual(callbacks['browse']('', '视频', '全部', '', 20)[1], [])
            def generate(asset_id):
                service.save(asset_id, 'ready', '动物', 'test', tags=['动物'])
            with patch('ui.library_page.CaptionService.describe', side_effect=generate) as model:
                updates = callbacks['complete_tags']('自然')
                next(updates)
                self.assertIn('正在加载标签', next(updates)[0])
                model.assert_not_called()
                list(updates)
                model.assert_called_once_with(ids[2])
            self.assertEqual(len(callbacks['inspect_tags']('动物')[4]), 1)

    def test_filters_search_selection_and_empty_search(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = Library(root / 'data')
            page = build_page(library, Encoder())
            callbacks = page.objectlift_callbacks
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
            detail, download, player, selected, frames, refs, preview, description = callbacks['select'](
                hits, gr.SelectData(None, {'index': 0, 'value': None}))
            self.assertTrue(Path(download).is_file())
            self.assertIn(scores[0][1], detail)
            empty = callbacks['search'](' ', 10)
            self.assertEqual(empty[0], [])
            self.assertEqual(empty[3], [])
