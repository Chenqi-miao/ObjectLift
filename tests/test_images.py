import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services.image_io import (ImageValidationError, crop_bounds, crop_target,
                               detection_rgb, load_image)
from services.foreground import validate_foreground


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'input.png'

    def test_orientation_and_resize(self):
        source = Image.new('RGB', (80, 40))
        exif = Image.Exif()
        exif[274] = 6
        source.save(self.path, exif=exif)
        result = load_image(self.path, max_side=40)
        self.assertEqual(result.size, (20, 40))
        self.assertNotIn(274, result.getexif())

    def test_palette_transparency(self):
        source = Image.new('P', (10, 10), 0)
        source.save(self.path, transparency=0)
        result = load_image(self.path)
        self.assertEqual(result.mode, 'RGBA')
        self.assertEqual(result.getpixel((0, 0))[3], 0)

    def test_corrupt_and_unsupported(self):
        self.path.write_bytes(b'not an image')
        with self.assertRaises(ImageValidationError):
            load_image(self.path)
        Image.new('RGB', (10, 10)).save(self.path, format='BMP')
        with self.assertRaises(ImageValidationError):
            load_image(self.path)

    def test_pixel_limit(self):
        Image.new('RGB', (10, 10)).save(self.path)
        with self.assertRaises(ImageValidationError):
            load_image(self.path, max_pixels=99)

    def test_crop_padding_and_clipping(self):
        image = Image.new('RGBA', (100, 80), (20, 30, 40, 50))
        self.assertEqual(crop_bounds(image, (10, 20, 50, 60), .1), (6, 16, 54, 64))
        self.assertEqual(crop_target(image, (-10, -10, 30, 30), 0).size, (30, 30))
        self.assertEqual(crop_target(image, (0, 0, 5, 5), 0).getpixel((0, 0)), (20, 30, 40, 50))

    def test_invalid_boxes(self):
        image = Image.new('RGB', (100, 80))
        for box in [(10, 0, 5, 20), (0, 0, 0, 1), (101, 0, 110, 10),
                    (float('nan'), 0, 10, 10), (-20, 0, -1, 10)]:
            with self.subTest(box=box), self.assertRaises(ImageValidationError):
                crop_target(image, box)
        with self.assertRaises(ImageValidationError):
            crop_target(image, (0, 0, 10, 10), -1)

    def test_rgb_composite_does_not_mutate(self):
        image = Image.new('RGBA', (10, 10), (255, 0, 0, 0))
        self.assertEqual(detection_rgb(image).getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 0))

    def test_foreground_validation(self):
        for image in [Image.new('RGB', (10, 10)), Image.new('RGBA', (10, 10)),
                      Image.new('RGBA', (1, 10), 'red')]:
            with self.assertRaises(ImageValidationError):
                validate_foreground(image)
        image = Image.new('RGBA', (10, 10))
        image.putpixel((5, 5), (200, 20, 10, 128))
        result = validate_foreground(image)
        self.assertEqual(result.getpixel((5, 5)), (200, 20, 10, 128))
        self.assertIsNot(result, image)


if __name__ == '__main__':
    unittest.main()
