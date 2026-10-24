"""Check an uploaded photo and prepare it for the extraction model.

The file's own content decides whether it is an image (not its name or the
type the browser claims). The prepared copy is turned upright from its EXIF
orientation, shrunk to the model's largest useful size and saved as a fresh
JPEG, which drops EXIF data such as the phone's location. The original photo
is never changed.
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

# MPO is the JPEG variant some phone cameras write.
ACCEPTED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}
MAX_FILE_BYTES = 20 * 1024 * 1024


class UnusableImage(ValueError):
    """The file cannot be used as a ledger photo; the message says why."""


def prepare_image(data: bytes, max_edge: int, jpeg_quality: int = 85) -> bytes:
    """An upright JPEG no larger than `max_edge` on its long side, without EXIF."""
    if len(data) > MAX_FILE_BYTES:
        raise UnusableImage(f"The file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ACCEPTED_FORMATS:
                raise UnusableImage(
                    f"{image.format} files are not accepted; use a JPEG, PNG or WebP photo."
                )
            image.load()
            upright = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as e:
        raise UnusableImage("The file could not be read as an image.") from e
    upright.thumbnail((max_edge, max_edge))  # only ever shrinks
    out = io.BytesIO()
    upright.save(out, format="JPEG", quality=jpeg_quality)
    return out.getvalue()
