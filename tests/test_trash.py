import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
from services.library import Library
from services.indexing import IndexService
from ui.library_page import build_page


class TrashTests(unittest.TestCase):
    def test_recycle_and_restore_preserve_files_and_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'image.png'
            Image.new('RGB', (30, 30)).save(source)
            library = Library(root / 'data')
            asset_id = library.import_image(source)['asset_id']
            encoder = SimpleNamespace(model_id='test', revision='v1', image=lambda p:[1,0], text=lambda q:[1,0])
            indexer = IndexService(library, encoder)
            list(indexer.index_pending())
            asset = library.get_asset(asset_id)
            original = library.root / asset['stored_path']
            page = build_page(library, encoder)
            result = page.objectlift_callbacks['remove_selected'](asset_id)
            self.assertIsNone(result[4])
            self.assertEqual(library.list_assets(), [])
            self.assertEqual(library.image_diagnostics(), [])
            self.assertEqual(library.statistics()['total'], 0)
            self.assertEqual(indexer.search('image'), [])
            self.assertIn('0', list(indexer.index_pending())[0])
            self.assertTrue(original.is_file())
            self.assertTrue(source.is_file())
            self.assertEqual(library.import_files([source])[0]['status'], 'in_trash')
            reopened = Library(library.root)
            self.assertEqual(len(reopened.list_trash()), 1)
            self.assertIn('恢复', page.objectlift_callbacks['restore_selected'](asset_id))
            self.assertEqual(len(indexer.search('image')), 1)
            self.assertEqual(library.get_asset(asset_id)['items'][0]['embedding'], asset['items'][0]['embedding'])
            self.assertEqual(library.list_trash(), [])
