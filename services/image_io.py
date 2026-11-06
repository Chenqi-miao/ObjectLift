"""All boxes use pixels of the EXIF-corrected, size-limited image."""
import math
import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


class ImageValidationError(ValueError):
    """Invalid or unsupported user image."""


def load_image(path: str | Path, max_side: int = 2048,
               max_pixels: int = 40_000_000) -> Image.Image:
    """Read JPG/PNG, correct orientation, preserve alpha, and bound dimensions.

    Returns a detached RGB/RGBA image. Detection and cropping must both use
    this returned image, not coordinates from the original uploaded file.
    """
    if max_side < 1 or max_pixels < 1:
        raise ValueError('Image limits must be positive.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as source:
                if source.format not in {'JPEG', 'PNG'}:
                    raise ImageValidationError('仅支持 JPG 和 PNG 图片。')
                if source.width * source.height > max_pixels:
                    raise ImageValidationError('图片像素过多，请缩小后上传。')
                if getattr(source, 'n_frames', 1) != 1:
                    raise ImageValidationError('请上传静态图片。')
                source.load()
                alpha = 'A' in source.getbands() or 'transparency' in source.info
                result = ImageOps.exif_transpose(source).convert('RGBA' if alpha else 'RGB')
                result.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
                return result
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageValidationError('图片像素过多，请缩小后上传。') from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ImageValidationError('无法读取图片，文件可能损坏或不可访问。') from exc


def crop_bounds(image: Image.Image, bbox: tuple[float, float, float, float],
                padding_ratio: float = 0.1) -> tuple[int, int, int, int]:
    """Expand by a fraction of box width/height on each side; clamp to image."""
    if len(bbox) != 4 or not all(math.isfinite(v) for v in bbox):
        raise ImageValidationError('裁剪坐标必须是四个有限数值。')
    if not math.isfinite(padding_ratio) or not 0 <= padding_ratio <= 1:
        raise ImageValidationError('裁剪边距必须在 0 到 1 之间。')
    x1, y1, x2, y2 = bbox
    if x2 <= x1 or y2 <= y1:
        raise ImageValidationError('裁剪框宽高必须大于零。')
    if x2 <= 0 or y2 <= 0 or x1 >= image.width or y1 >= image.height:
        raise ImageValidationError('裁剪框位于图片之外。')
    dx, dy = (x2 - x1) * padding_ratio, (y2 - y1) * padding_ratio
    return (max(0, math.floor(x1 - dx)), max(0, math.floor(y1 - dy)),
            min(image.width, math.ceil(x2 + dx)), min(image.height, math.ceil(y2 + dy)))


def crop_target(image: Image.Image, bbox: tuple[float, float, float, float],
                padding_ratio: float = 0.1) -> Image.Image:
    return image.crop(crop_bounds(image, bbox, padding_ratio))


def detection_rgb(image: Image.Image) -> Image.Image:
    """Composite transparency onto white for detection without changing size."""
    rgba = image.convert('RGBA')
    background = Image.new('RGBA', image.size, 'white')
    return Image.alpha_composite(background, rgba).convert('RGB')
