from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select

from flower.auth import get_db, require_user, owned_plant
from flower.models import (
    Plant,
    Device,
    DeviceStatus,
    Command,
    CareProfile,
    FallbackPolicy,
    PlantImage,
    Job,
    utcnow,
)
from flower.schemas import WaterRequest, SpeciesConfirmation, PlantInput, serialize
from flower.services.commands import create_command
from flower.errors import DomainError

router = APIRouter(prefix="/api/v1")


@router.get("/plants")
def plants(user=Depends(require_user), db=Depends(get_db)):
    return [serialize(p) for p in db.scalars(select(Plant).where(Plant.user_id == user.id))]


@router.get("/devices")
def devices(user=Depends(require_user), db=Depends(get_db)):
    return [
        {"id": d.id, "name": d.name, "device_code": d.device_code, "source_type": d.source_type}
        for d in db.scalars(select(Device).where(Device.owner_user_id == user.id))
    ]


@router.post("/plants", status_code=201)
def add_plant(data: PlantInput, user=Depends(require_user), db=Depends(get_db)):
    try:
        device_id = str(UUID(data.device_id))
    except ValueError:
        raise DomainError("INVALID_DEVICE_ID", status=422) from None
    device = db.get(Device, device_id)
    if not device or device.owner_user_id != user.id:
        raise DomainError("NOT_FOUND", status=404)
    plant = Plant(user_id=user.id, **data.model_dump())
    db.add(plant)
    db.flush()
    return serialize(plant)


@router.post("/plants/{plant_id}/capture", status_code=202)
def capture(
    plant_id: UUID,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=100),
    user=Depends(require_user),
    db=Depends(get_db),
):
    plant = owned_plant(db, str(plant_id), user.id)
    command = create_command(
        db,
        request.app.state.settings,
        device_id=plant.device_id,
        plant_id=plant.id,
        user_id=user.id,
        capability="camera",
        action="capture",
        parameters={"shots": ["whole", "leaf", "flower"]},
        source="user_manual",
        run_mode=request.app.state.settings.run_mode,
        idempotency_key=idempotency_key,
    )
    return serialize(command)


@router.get("/plants/{plant_id}/recognition")
def recognition(plant_id: UUID, user=Depends(require_user), db=Depends(get_db)):
    plant = owned_plant(db, str(plant_id), user.id)
    capture = db.scalar(
        select(Command)
        .where(Command.plant_id == plant.id, Command.action == "capture")
        .order_by(Command.created_at.desc())
        .limit(1)
    )
    response = {
        "result": None,
        "status": "empty",
        "capture_id": capture.id if capture else None,
        "image_id": None,
        "default_selection": None,
        "retake_recommended": False,
        "manual_input_available": True,
    }
    query = select(PlantImage).where(
        PlantImage.plant_id == plant.id, PlantImage.image_type.in_(["whole", "leaf", "flower"])
    )
    if capture:
        if capture.status != "succeeded":
            return response | {"status": "capture_" + capture.status}
        if not capture.started_at or not capture.finished_at:
            return response | {"status": "image_missing"}
        query = query.where(
            PlantImage.created_at >= capture.started_at,
            PlantImage.created_at <= capture.finished_at,
        )
    image = db.scalar(query.order_by(PlantImage.created_at.desc(), PlantImage.id.desc()).limit(1))
    if not image:
        return response | {"status": "image_missing" if capture else "empty"}
    response["image_id"] = image.id
    if not image.recognition_result:
        job = db.scalar(
            select(Job)
            .where(Job.target_id == image.id, Job.job_type == "plant_recognition")
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        return response | {"status": job.status if job and job.status != "succeeded" else "failed"}
    result = {
        **image.recognition_result,
        "candidates": sorted(
            image.recognition_result["candidates"],
            key=lambda candidate: candidate["confidence"],
            reverse=True,
        ),
    }
    confidence = result["candidates"][0]["confidence"]
    return response | {
        "result": result,
        "status": "succeeded",
        "default_selection": 0 if confidence >= 0.75 else None,
        "retake_recommended": confidence < 0.45,
    }


@router.post("/plants/{plant_id}/confirm-species")
def confirm_species(
    plant_id: UUID, data: SpeciesConfirmation, user=Depends(require_user), db=Depends(get_db)
):
    plant = owned_plant(db, str(plant_id), user.id)
    # Serialize with command creation and profile activation on this device.
    db.refresh(db.get(Device, plant.device_id), with_for_update=True)
    db.refresh(plant, with_for_update=True)
    if db.scalar(
        select(Command.id).where(
            Command.plant_id == plant.id,
            Command.action == "dispense",
            Command.status.in_(["pending", "claimed", "executing"]),
        )
    ):
        raise DomainError("ACTIVE_COMMAND")
    image = None
    if data.image_id:
        image = db.scalar(
            select(PlantImage)
            .where(
                PlantImage.id == str(data.image_id),
                PlantImage.plant_id == plant.id,
                PlantImage.device_id == plant.device_id,
                PlantImage.image_type.in_(["whole", "leaf", "flower"]),
            )
            .with_for_update()
        )
        if image is None:
            raise DomainError("NOT_FOUND", status=404)
    plant.common_name, plant.scientific_name = data.common_name, data.scientific_name
    plant.input_method, plant.recognition_confidence = data.input_method, data.confidence
    plant.recognition_confirmed, plant.auto_mode = True, False
    now = utcnow()
    for profile in db.scalars(select(CareProfile).where(CareProfile.plant_id == plant.id)):
        profile.confirmed = False
        profile.valid_until = min(profile.valid_until, now)
    for policy in db.scalars(select(FallbackPolicy).where(FallbackPolicy.plant_id == plant.id)):
        policy.valid_until = min(policy.valid_until, now)
    if image:
        image.expires_at = None
        plant.photo_path = image.file_path
    return serialize(plant)


@router.post("/plants/{plant_id}/water", status_code=202)
def water(
    plant_id: UUID,
    data: WaterRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=100),
    user=Depends(require_user),
    db=Depends(get_db),
):
    request.app.state.rate_limiter.check("water:" + user.id)
    plant = owned_plant(db, str(plant_id), user.id)
    command = create_command(
        db,
        request.app.state.settings,
        device_id=plant.device_id,
        plant_id=plant.id,
        user_id=user.id,
        capability="dispenser",
        action="dispense",
        parameters=data.model_dump(),
        source="user_manual",
        run_mode=request.app.state.settings.run_mode,
        idempotency_key=idempotency_key,
    )
    return serialize(command)


@router.get("/plants/{plant_id}/status")
def status(plant_id: UUID, user=Depends(require_user), db=Depends(get_db)):
    plant = owned_plant(db, str(plant_id), user.id)
    current = db.get(DeviceStatus, plant.device_id)
    latest = db.scalar(
        select(Command)
        .where(Command.plant_id == plant.id)
        .order_by(Command.created_at.desc())
        .limit(1)
    )
    from flower.models import Event, WateringSession
    from flower.schemas import CalibrationInput

    device = db.get(Device, plant.device_id)
    try:
        CalibrationInput.model_validate(device.calibration)
        calibrated = True
    except ValueError:
        calibrated = False
    profile = db.scalar(
        select(CareProfile)
        .where(CareProfile.plant_id == plant.id)
        .order_by(CareProfile.version.desc())
        .limit(1)
    )
    decision = db.scalar(
        select(Event)
        .where(Event.plant_id == plant.id, Event.event_type == "decision")
        .order_by(Event.occurred_at.desc())
        .limit(1)
    )
    last_water = db.scalar(
        select(WateringSession)
        .where(WateringSession.plant_id == plant.id, WateringSession.actual_ml > 0)
        .order_by(WateringSession.occurred_at.desc())
        .limit(1)
    )
    image = (
        db.scalar(select(PlantImage).where(PlantImage.file_path == plant.photo_path))
        if plant.photo_path
        else None
    )
    detail = serialize(current) if current else None
    if detail:
        detail.update(
            time_trusted=device.time_trusted,
            calibration_valid=calibrated,
            firmware_version=device.firmware_version,
            last_seen_at=device.last_seen_at,
        )
        if not device.last_seen_at or (utcnow() - device.last_seen_at).total_seconds() > 90:
            detail["operating_mode"] = "SAFE_HOLD"
            detail["fault_codes"] = list(set(detail["fault_codes"]) | {"CLOUD_OFFLINE"})
    return {
        "plant": serialize(plant),
        "device": detail,
        "command": serialize(latest) if latest else None,
        "care_profile": serialize(profile) if profile else None,
        "decision": decision.event_data if decision else None,
        "last_watering": serialize(last_water) if last_water else None,
        "photo_id": image.id if image else None,
        "spec_version": "2.2.2",
    }
