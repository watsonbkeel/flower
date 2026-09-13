from datetime import timedelta
from io import BytesIO
from pathlib import Path
import shutil
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from flower.errors import DomainError
from flower.models import PlantImage, utcnow


def free_bytes(path):
    path = Path(path)
    while not path.exists():
        path = path.parent
    return shutil.disk_usage(path).free


def store_image(settings, content, mime, device, plant_id, image_type):
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise DomainError("UPLOAD_TOO_LARGE", status=413)
    if free_bytes(settings.upload_dir) - len(content) < settings.min_upload_free_bytes:
        raise DomainError("STORAGE_LOW", "存储空间不足，暂时无法接收图片", status=507)
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"JPEG", "PNG"} or mime != Image.MIME[image.format]:
                raise ValueError()
            if not (
                128 <= image.width <= 4096
                and 128 <= image.height <= 4096
                and image.width * image.height <= 12_000_000
            ):
                raise ValueError()
            image.verify()
        output = BytesIO()
        with Image.open(BytesIO(content)) as image:
            image.convert("RGB").save(output, format="JPEG", quality=85)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise DomainError("INVALID_IMAGE", status=422) from None
    now = utcnow()
    relative = f"{now:%Y/%m}/{uuid4()}.jpg"
    path = settings.upload_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(output.getvalue())
    return PlantImage(
        device_id=device.id,
        plant_id=plant_id,
        file_path=relative,
        image_type=image_type,
        source_type=device.source_type,
        expires_at=now + timedelta(days=settings.image_retention_days),
    )


def image_path(settings, relative):
    path = (settings.upload_dir / relative).resolve()
    if not path.is_relative_to(settings.upload_dir.resolve()) or not path.is_file():
        raise DomainError("IMAGE_NOT_FOUND", status=404)
    return path
