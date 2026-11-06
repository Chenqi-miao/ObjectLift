"""Immutable processing snapshots, isolated by random directory per operation."""
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image

from services.image_io import load_image, crop_bounds
from services.foreground import validate_foreground


class Workspace:
    def __init__(self, root='jobs'):
        self.root = Path(root).resolve()

    def save(self, image: Image.Image, stage: str, parent=None, **metadata):
        directory = self.root / uuid4().hex
        directory.mkdir(parents=True)
        image.save(directory / 'image.png')
        manifest = dict(job_id=directory.name, stage=stage, parent=parent,
                        created_at=datetime.now(timezone.utc).isoformat(),
                        image_size=list(image.size), mode=image.mode,
                        reconstruction_status='not_available', **metadata)
        (directory / 'manifest.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return dict(id=directory.name, image=str(directory / 'image.png'),
                    manifest=str(directory / 'manifest.json'))

    def upload(self, path):
        return self.save(load_image(path), 'uploaded')

    def crop(self, source, bbox, padding):
        image = load_image(source['image'])
        bounds = crop_bounds(image, bbox, padding)
        return self.save(image.crop(bounds), 'cropped', source['id'],
                         bbox_xyxy=list(bbox), actual_bbox=list(bounds), padding=padding)

    def foreground(self, path, parent=None):
        image = validate_foreground(load_image(path))
        return self.save(image, 'foreground_ready', parent,
                         warning='单图重建的背面和遮挡区域为推测；不恢复真实尺寸。')
