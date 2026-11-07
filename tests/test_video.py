import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from services.library import Library
from services.indexing import IndexService


class Encoder:
    model_id = 'video-test'
    revision = 'v1'

    def image(self, path):
        with Image.open(path) as image:
            image.load()
        return [1, 0]

    def text(self, query):
        return [1, 0]


class VideoTests(unittest.TestCase):
    def test_import_index_merge_and_persistence(self):
        def extract(source, output):
            output.mkdir()
            frames = []
            for index, timestamp in enumerate([0, 5040, 10080]):
                frame = output / f'frame-{index:03}.png'
                Image.new('RGB', (32, 24)).save(frame)
                frames.append((frame, timestamp))
            return 32, 24, 12000, frames

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'clip.mp4'
            source.write_bytes(b'test fixture, decoder mocked')
            library = Library(root / 'data')
            with patch('services.library.extract_video', side_effect=extract) as decoder:
                first, second = library.import_files([source, source])
                self.assertEqual(second['status'], 'duplicate')
                self.assertEqual(decoder.call_count, 1)
            index = IndexService(library, Encoder())
            list(index.index_pending())
            hits = index.search('test', media_type='video')
            self.assertEqual([h['timestamp_ms'] for h in hits], [0, 10080])
            self.assertEqual(index.search('test', media_type='image'), [])
            reopened = Library(library.root).get_asset(first['asset_id'])
            self.assertEqual(len(reopened['items']), 3)
            self.assertEqual(source.read_bytes(), (library.root / reopened['stored_path']).read_bytes())

    def test_decode_failure_does_not_register_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'bad.mp4'
            source.write_bytes(b'bad')
            library = Library(Path(directory) / 'data')
            with patch('services.library.extract_video', side_effect=ValueError('invalid')):
                self.assertEqual(library.import_files([source])[0]['status'], 'failed')
            self.assertEqual(library.list_assets(), [])
