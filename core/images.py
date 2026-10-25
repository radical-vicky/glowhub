from io import BytesIO
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 40_000_000  # decompression-bomb guard


def clean_image(upload, max_px=2000, max_mb=5):
    """Validate real image content, strip metadata (EXIF/GPS), re-encode as JPEG with a random name."""
    if upload.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Image must be under {max_mb} MB.")
    try:
        Image.open(upload).verify()
        upload.seek(0)
        img = Image.open(upload)
        if img.format not in ("JPEG", "PNG", "WEBP"):
            raise ValueError
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        raise ValidationError("Upload a JPEG, PNG or WebP image.")
    img.thumbnail((max_px, max_px))
    out = BytesIO()
    img.save(out, "JPEG", quality=85)
    return ContentFile(out.getvalue(), name=f"{uuid4().hex}.jpg")
