import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from services.workspace import Workspace


class WorkspaceTests(unittest.TestCase):
    def test_pipeline_preserves_parent_and_isolates_results(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'source.png'
            Image.new('RGBA', (40, 40), (100, 0, 0, 128)).save(image)
            workspace = Workspace(Path(directory) / 'jobs')
            source = workspace.upload(image)
            crop = workspace.crop(source, (5, 5, 30, 30), 0)
            fg = workspace.foreground(crop['image'], crop['id'])
            second = workspace.upload(image)
            self.assertEqual(len({r['id'] for r in [source, crop, fg, second]}), 4)
            manifest = json.loads(Path(fg['manifest']).read_text(encoding='utf-8'))
            self.assertEqual(manifest['parent'], crop['id'])
            self.assertEqual(manifest['image_size'], [25, 25])
            self.assertEqual(manifest['reconstruction_status'], 'not_available')
            with Image.open(source['image']) as original:
                self.assertEqual(original.size, (40, 40))

    def test_invalid_foreground_does_not_create_result(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'source.png'
            Image.new('RGBA', (10, 10)).save(image)
            workspace = Workspace(Path(directory) / 'jobs')
            with self.assertRaises(ValueError):
                workspace.foreground(image)
            self.assertFalse(workspace.root.exists())
