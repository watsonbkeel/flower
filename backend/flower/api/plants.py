from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select

from flower.auth import get_db, require_user, owned_plant
from flower.models import Plant, DeviceStatus, Command
from flower.schemas import WaterRequest, serialize
from flower.services.commands import create_command

router = APIRouter(prefix="/api/v1")


@router.get("/plants")
def plants(user=Depends(require_user), db=Depends(get_db)):
    return [serialize(p) for p in db.scalars(select(Plant).where(Plant.user_id == user.id))]


@router.post("/plants/{plant_id}/water", status_code=202)
def water(
    plant_id: UUID,
    data: WaterRequest,
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
    return {
        "plant": serialize(plant),
        "device": serialize(current) if current else None,
        "command": serialize(latest) if latest else None,
        "spec_version": "2.2.2",
    }
