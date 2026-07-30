from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.core.files.storage import Storage
from django.core.exceptions import ValidationError
from django.db import transaction
from PIL import Image, UnidentifiedImageError

MAX_PROFILE_IMAGE_BYTES = 5 * 1024 * 1024
MAX_DIMENSION = 1600
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def optimize_profile_image(uploaded_file: UploadedFile) -> ContentFile:
    if uploaded_file.size and uploaded_file.size > MAX_PROFILE_IMAGE_BYTES:
        raise ValidationError("Image must be 5 MB or smaller.")

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            image_format = (image.format or "").upper()
            if image_format not in ALLOWED_FORMATS:
                raise ValidationError("Only JPEG, PNG, or WEBP images are allowed.")
            image.load()
            sanitized = image.copy()
    except UnidentifiedImageError as exc:
        raise ValidationError("Upload a valid image file.") from exc

    if sanitized.mode not in {"RGB", "RGBA"}:
        sanitized = sanitized.convert("RGBA" if "A" in sanitized.getbands() else "RGB")
    if max(sanitized.size) > MAX_DIMENSION:
        sanitized.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

    output = BytesIO()
    save_kwargs = {"format": "WEBP", "quality": 82, "method": 6}
    if sanitized.mode == "RGBA":
        save_kwargs["lossless"] = False
    sanitized.save(output, **save_kwargs)

    content = ContentFile(output.getvalue())
    content.name = f"{uuid4().hex}.webp"
    return content


def schedule_storage_delete(storage: Storage, name: str | None) -> None:
    if not name:
        return
    transaction.on_commit(lambda: storage.delete(name))
