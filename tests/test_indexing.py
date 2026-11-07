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
