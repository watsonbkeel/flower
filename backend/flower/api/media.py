from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from flower.auth import get_db, require_device, require_user
from flower.errors import DomainError
from flower.models import Plant, PlantImage, Job
from flower.schemas import serialize
from flower.services.alerts import alert
from flower.services.images import store_image, image_path
from flower.services.jobs import enqueue_job

router = APIRouter(prefix="/api/v1")


@router.post("/images", status_code=201)
def upload_memory(
    request: Request,
    plant_id: UUID = Form(),
    file: UploadFile = File(),
    user=Depends(require_user),
    db=Depends(get_db),
):
    from flower.auth import owned_plant
    from flower.models import Device

    plant = owned_plant(db, str(plant_id), user.id)
    device = db.get(Device, plant.device_id)
    settings = request.app.state.settings
    image = store_image(
        settings,
        file.file.read(settings.max_upload_mb * 1024 * 1024 + 1),
        file.content_type,
        device,
        plant.id,
        "memory",
    )
    try:
        db.add(image)
        db.flush()
        db.commit()
    except Exception:
        (settings.upload_dir / image.file_path).unlink(missing_ok=True)
        raise
    return {"image_id": image.id, "source_type": image.source_type}


@router.post("/device/images", status_code=202)
def upload(
    request: Request,
    plant_id: UUID = Form(),
    image_type: str = Form(),
    file: UploadFile = File(),
    device=Depends(require_device),
    db=Depends(get_db),
):
    plant = db.scalar(select(Plant).where(Plant.id == str(plant_id), Plant.device_id == device.id))
    if not plant:
        raise DomainError("NOT_FOUND", status=404)
    if image_type not in {"whole", "leaf", "flower", "memory"}:
        raise DomainError("INVALID_IMAGE_TYPE", status=422)
    settings = request.app.state.settings
    content = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    try:
        image = store_image(settings, content, file.content_type, device, plant.id, image_type)
    except DomainError as exc:
        if exc.code == "STORAGE_LOW":
            alert(db, device, "STORAGE_LOW", exc.message, plant_id=plant.id)
            db.commit()
        raise
    try:
        db.add(image)
        db.flush()
        job = enqueue_job(
            db,
            "plant_recognition",
            "image",
            image.id,
            device.owner_user_id,
            f"recognition:{image.id}",
        )
        db.commit()
    except Exception:
        (settings.upload_dir / image.file_path).unlink(missing_ok=True)
        raise
    return {"image_id": image.id, "job_id": job.id, "source_type": image.source_type}


@router.get("/images/{image_id}")
def get_image(image_id: UUID, request: Request, user=Depends(require_user), db=Depends(get_db)):
    from flower.models import Device

    image = db.scalar(
        select(PlantImage)
        .join(Device, PlantImage.device_id == Device.id)
        .where(PlantImage.id == str(image_id), Device.owner_user_id == user.id)
    )
    if not image:
        raise DomainError("NOT_FOUND", status=404)
    return FileResponse(
        image_path(request.app.state.settings, image.file_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/jobs/{job_id}")
def get_job(job_id: UUID, user=Depends(require_user), db=Depends(get_db)):
    job = db.scalar(select(Job).where(Job.id == str(job_id), Job.user_id == user.id))
    if not job:
        raise DomainError("NOT_FOUND", status=404)
    return serialize(job)
