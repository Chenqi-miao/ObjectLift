import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from services.library import Library
from services.indexing import IndexService, normalize


class Encoder:
    model_id = 'test-only'
    revision = 'test-v1'
    fail = False

    def image(self, path):
        if self.fail:
            raise ValueError('test failure')
        return [1, 0]

    def text(self, query):
        return [1, 0]


class IndexTests(unittest.TestCase):
    def test_retry_only_selected_asset_and_skip_ready(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            library = Library(root / 'data')
            ids = []
            for color in ['red', 'blue']:
                path = root / f'{color}.png'
                Image.new('RGB', (10, 10), color).save(path)
                ids.append(library.import_image(path)['asset_id'])
            encoder = Encoder()
            encoder.image = Mock(return_value=[1, 0])
            service = IndexService(library, encoder)
            list(service.index_pending(asset_id=ids[0]))
            self.assertEqual(library.get_asset(ids[1])['items'][0]['embedding_status'], 'pending')
            list(service.index_pending(asset_id=ids[0]))
            self.assertEqual(encoder.image.call_count, 1)
            encoder.image.side_effect = ValueError('failure')
            list(service.index_pending(asset_id=ids[1]))
            encoder.image.side_effect = None
            list(service.index_pending(asset_id=ids[1]))
            self.assertEqual(library.get_asset(ids[1])['items'][0]['embedding_status'], 'ready')

    def test_query_cache_revision_and_busy(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'image.png'
            Image.new('RGB', (10, 10)).save(path)
            library = Library(Path(folder) / 'data')
            library.import_image(path)
            encoder = Encoder()
            encoder.text = Mock(return_value=[1, 0])
            service = IndexService(library, encoder)
            self.assertGreaterEqual(service.warmup(), 0)
            encoder.text.reset_mock()
            list(service.index_pending())
            first = service.search('图片')
            self.assertEqual(service.search(' 图片 ', limit=1), first)
            self.assertEqual(encoder.text.call_count, 1)
            self.assertTrue(service.last_search_stats['cache_hit'])
            encoder.revision = 'changed'
            list(service.index_pending())
            service.search('图片')
            self.assertEqual(encoder.text.call_count, 2)
            with service.lock:
                with self.assertRaisesRegex(ValueError, '正在运行'):
                    service.search('图片')

    def test_retry_persistence_and_revision_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'image.png'
            Image.new('RGB', (10, 10)).save(path)
            lib = Library(Path(folder) / 'data')
            asset_id = lib.import_image(path)['asset_id']
            encoder = Encoder()
            service = IndexService(lib, encoder)
            encoder.fail = True
            list(service.index_pending())
            self.assertEqual(lib.get_asset(asset_id)['status'], 'failed')
            encoder.fail = False
            list(service.index_pending())
            self.assertEqual(lib.get_asset(asset_id)['status'], 'partial')
            self.assertAlmostEqual(service.search('图片')[0]['similarity'], 1)
            reopened = IndexService(Library(lib.root), encoder)
            self.assertEqual(len(reopened.search('图片')), 1)
            encoder.revision = 'test-v2'
            self.assertEqual(reopened.search('图片'), [])
            list(reopened.index_pending())
            self.assertEqual(len(reopened.search('图片')), 1)

    def test_invalid_vectors(self):
        for value in ([0, 0], [np.nan, 1], [[1, 2]], []):
            with self.assertRaises(ValueError):
                normalize(value)
