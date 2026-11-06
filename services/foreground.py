"""Offline foreground validation; automatic background removal is separate."""
from PIL import Image

from services.image_io import ImageValidationError


def validate_foreground(image: Image.Image) -> Image.Image:
    """Return RGBA copy; reject missing alpha or completely empty foreground.

    Opaque RGBA is allowed: alpha alone cannot establish segmentation quality.
    No centering, scaling or compositing is performed here; the reconstruction
    worker owns that preprocessing so it cannot accidentally be applied twice.
    """
    if image.width < 2 or image.height < 2:
        raise ImageValidationError('前景图片宽高至少为 2 像素。')
    if 'A' not in image.getbands() and 'transparency' not in image.info:
        raise ImageValidationError('请提供带透明通道的 PNG 前景。')
    result = image.convert('RGBA')
    if result.getchannel('A').getbbox() is None:
        raise ImageValidationError('前景完全透明，请重新选择物体。')
    return result
