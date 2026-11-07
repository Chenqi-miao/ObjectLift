import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

from PIL import Image
from services.library import Library
from services.captions import CaptionService, normalize_tags


class CaptionTests(unittest.TestCase):
    def test_unclassified_fallback(self):
        for tags in (None, [], ['几何图形'], ['未分类']):
            self.assertEqual(normalize_tags(tags), ['未分类'])
        self.assertEqual(normalize_tags(['动物', '昆虫', '动物']), ['动物'])
        with self.assertRaises(ValueError):
            normalize_tags([123])

    def test_image_tags_replace_and_filter(self):
        from services.indexing import IndexService
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'image.png'
            Image.new('RGB', (20, 20)).save(source)
            library = Library(root / 'data')
            asset_id = library.import_image(source)['asset_id']
            encoder = SimpleNamespace(model_id='test', revision='test', image=lambda p: [1, 0], text=lambda q: [1, 0])
            indexer = IndexService(library, encoder)
            list(indexer.index_pending())
            service = CaptionService(library, indexer)
            service.save(asset_id, 'ready', '植物', 'test', tags=['自然'])
            self.assertEqual(library.get_asset(asset_id)['status'], 'ready')
            self.assertEqual(len(indexer.search('植物', tag='自然')), 1)
            self.assertEqual(indexer.search('植物', tag='动物'), [])
            service.save(asset_id, 'ready', '花盆', 'test', tags=['物品', '物品'])
            self.assertEqual(library.get_asset(asset_id)['items'][0]['tags'], ['物品'])
            self.assertEqual(indexer.search('植物', tag='自然'), [])
            service.save(asset_id, 'failed', error='failure')
            self.assertEqual(library.get_asset(asset_id)['items'][0]['caption'], '花盆')

    def test_sample_persistence_failure_and_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = Library(root / 'data')
            source = root / 'sample.png'
            Image.new('RGB', (20, 20)).save(source)
            asset_id = library.import_image(source)['asset_id']
            with library.connection() as db:
                db.execute("UPDATE assets SET media_type='video', duration_ms=1000")
                db.execute('UPDATE visual_items SET timestamp_ms=0')
            indexer = SimpleNamespace(lock=threading.Lock(), encoder=SimpleNamespace(unload=Mock()))
            service = CaptionService(library, indexer)
            service.model_path = root
            (root / 'revision.json').write_text(json.dumps({'revision': 'test'}))
            (root / 'ready.json').write_text(json.dumps({'revision': 'test'}))

            def worker(args, **kwargs):
                request = json.loads(Path(args[2]).read_text())
                self.assertEqual(request['frames'][0]['timestamp_ms'], 0)
                Path(args[3]).write_text(json.dumps({'caption': '测试摘要'}), encoding='utf-8')
                return SimpleNamespace(returncode=0)

            with patch('services.captions.subprocess.run', side_effect=worker):
                self.assertEqual(service.describe(asset_id), '测试摘要')
            self.assertEqual(Library(library.root).get_asset(asset_id)['description']['caption'], '测试摘要')
            indexer.encoder.unload.assert_called_once()
            with patch('services.captions.subprocess.run', side_effect=ValueError('test failure')):
                with self.assertRaises(ValueError):
                    service.describe(asset_id)
            result = library.get_asset(asset_id)['description']
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['caption'], '测试摘要')
            self.assertFalse(indexer.lock.locked())
            service.save(asset_id, 'processing')
            library.recover_interrupted()
            self.assertEqual(library.get_asset(asset_id)['description']['status'], 'failed')
