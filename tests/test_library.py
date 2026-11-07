import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services.library import Library


class LibraryTests(unittest.TestCase):
    def test_import_duplicate_restart_and_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'photo.png'
            Image.new('RGB', (900, 600), 'red').save(source)
            original = source.read_bytes()
            library = Library(root / 'data')
            first, duplicate = library.import_files([source, source])
            self.assertEqual(first['status'], 'imported')
            self.assertEqual(duplicate['status'], 'duplicate')
            reopened = Library(root / 'data')
            self.assertEqual(len(reopened.list_assets()), 1)
            asset = reopened.get_asset(first['asset_id'])
            self.assertEqual((asset['width'], asset['height']), (900, 600))
            self.assertEqual((reopened.root / asset['stored_path']).read_bytes(), original)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(asset['items'][0]['embedding_status'], 'pending')
            with Image.open(reopened.root / asset['items'][0]['preview_path']) as preview:
                self.assertEqual(preview.size, (512, 341))

    def test_batch_failure_isolation_and_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bad, good = root / 'bad.png', root / 'good.png'
            bad.write_text('invalid image')
            Image.new('RGB', (20, 10)).save(good)
            library = Library(root / 'data')
            results = library.import_files([bad, good])
            self.assertEqual([r['status'] for r in results], ['failed', 'imported'])
            with library.connection() as db:
                db.execute("UPDATE visual_items SET caption_status='processing', embedding_status='ready'")
                db.execute("UPDATE assets SET status='processing'")
            library.recover_interrupted()
            asset = library.get_asset(results[1]['asset_id'])
            self.assertEqual(asset['status'], 'pending')
            self.assertEqual(asset['items'][0]['caption_status'], 'pending')
            self.assertEqual(asset['items'][0]['embedding_status'], 'ready')


if __name__ == '__main__':
    unittest.main()
