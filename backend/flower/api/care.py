from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select

from flower.auth import get_db, require_user, owned_plant
from flower.errors import DomainError
from flower.models import (
    CareProfile,
    Device,
    Memory,
    Plant,
    PlantImage,
    Command,
    WateringSession,
    utcnow,
)
from flower.schemas import ProfileConfirmation, Toggle, MemoryInput, MemoryEnabled, serialize
from flower.services.care import issue_fallback
from flower.services.commands import safety_context
from flower.services.jobs import enqueue_job
from flower.services.knowledge import MemoryRule

router = APIRouter(prefix="/api/v1")


@router.post("/plants/{plant_id}/care-profile/generate", status_code=202)
def generate(
    plant_id: UUID,
    idempotency_key: str | None = Header(default=None, min_length=1, max_length=100),
    user=Depends(require_user),
    db=Depends(get_db),
):
    plant = owned_plant(db, str(plant_id), user.id)
    if not plant.recognition_confirmed:
        raise DomainError("SPECIES_UNCONFIRMED")
    job = enqueue_job(
        db,
        "care_research",
        "plant",
        plant.id,
        user.id,
        f"care:{user.id}:{plant.id}:{idempotency_key or uuid4()}",
    )
    return {"job_id": job.id}


@router.post("/plants/{plant_id}/care-profile/confirm")
def confirm(
    plant_id: UUID,
    data: ProfileConfirmation,
    request: Request,
    user=Depends(require_user),
    db=Depends(get_db),
):
    plant = owned_plant(db, str(plant_id), user.id)
    db.refresh(db.get(Device, plant.device_id), with_for_update=True)
    db.refresh(plant, with_for_update=True)
    profile = db.scalar(
        select(CareProfile)
        .where(CareProfile.id == str(UUID(data.profile_id)), CareProfile.plant_id == plant.id)
        .with_for_update()
    )
    if not profile or profile.valid_until <= utcnow():
        raise DomainError("PROFILE_MISSING")
    if (
        request.app.state.settings.app_env == "production"
        and profile.profile.get("source_type") != "real"
    ):
        raise DomainError("MOCK_PROFILE_IN_PRODUCTION")
    if not profile.confirmed:
        profile.confirmed, profile.confirmed_at = True, utcnow()
        issue_fallback(db, request.app.state.settings, plant, profile)
    return serialize(profile)


@router.put("/plants/{plant_id}/auto-mode")
def auto_mode(
    plant_id: UUID, data: Toggle, request: Request, user=Depends(require_user), db=Depends(get_db)
):
    plant = owned_plant(db, str(plant_id), user.id)
    device = db.get(Device, plant.device_id)
    db.refresh(device, with_for_update=True)
    db.refresh(plant, with_for_update=True)
    if data.enabled:
        _, profile, _ = safety_context(
            db, request.app.state.settings, device, plant, utcnow(), source="user_manual"
        )
        issue_fallback(db, request.app.state.settings, plant, profile)
        plant.auto_mode_since = utcnow()
    else:
        for command in db.scalars(
            select(Command)
            .where(
                Command.plant_id == plant.id,
                Command.source == "cloud_auto",
                Command.status == "pending",
            )
            .with_for_update()
        ):
            command.status, command.finished_at = "cancelled", utcnow()
            session = db.scalar(
                select(WateringSession).where(WateringSession.command_id == command.id)
            )
            if session:
                session.quota_ml, session.status = 0, "final"
    plant.auto_mode = data.enabled
    return {"auto_mode": plant.auto_mode, "device_sync": "pending"}


def owned_memory(db, memory_id, user_id):
    memory = db.scalar(select(Memory).where(Memory.id == str(memory_id), Memory.user_id == user_id))
    if not memory:
        raise DomainError("NOT_FOUND", status=404)
    return memory


@router.get("/memories")
def memories(user=Depends(require_user), db=Depends(get_db)):
    return [
        serialize(m)
        | {
            "photo_id": db.scalar(select(PlantImage.id).where(PlantImage.file_path == m.photo_path))
            if m.photo_path
            else None
        }
        for m in db.scalars(
            select(Memory).where(Memory.user_id == user.id).order_by(Memory.created_at.desc())
        )
    ]


def apply_memory(db, memory, data, user):
    if data.plant_id:
        owned_plant(db, str(UUID(data.plant_id)), user.id)
    memory.plant_id, memory.title = data.plant_id, data.title
    memory.story, memory.original_experience = data.story, data.original_experience
    memory.structured_rule, memory.rule_confirmed, memory.rule_enabled = None, False, False
    if data.photo_id:
        image = db.scalar(
            select(PlantImage)
            .join(Device, Device.id == PlantImage.device_id)
            .where(PlantImage.id == str(UUID(data.photo_id)), Device.owner_user_id == user.id)
        )
        if not image:
            raise DomainError("NOT_FOUND", status=404)
        image.expires_at = None
        memory.photo_path = image.file_path


@router.post("/memories", status_code=201)
def add_memory(data: MemoryInput, user=Depends(require_user), db=Depends(get_db)):
    memory = Memory(user_id=user.id)
    apply_memory(db, memory, data, user)
    db.add(memory)
    db.flush()
    return serialize(memory)


@router.put("/memories/{memory_id}")
def update_memory(
    memory_id: UUID, data: MemoryInput, user=Depends(require_user), db=Depends(get_db)
):
    memory = owned_memory(db, memory_id, user.id)
    apply_memory(db, memory, data, user)
    return serialize(memory)


@router.post("/memories/{memory_id}/structure-rule", status_code=202)
def structure(
    memory_id: UUID,
    idempotency_key: str | None = Header(default=None, min_length=1, max_length=100),
    user=Depends(require_user),
    db=Depends(get_db),
):
    memory = owned_memory(db, memory_id, user.id)
    if not memory.original_experience:
        raise DomainError("EXPERIENCE_REQUIRED")
    job = enqueue_job(
        db,
        "memory_structure",
        "memory",
        memory.id,
        user.id,
        f"memory:{user.id}:{memory.id}:{idempotency_key or uuid4()}",
    )
    return {"job_id": job.id}


@router.put("/memories/{memory_id}/enabled")
def enable(
    memory_id: UUID,
    data: MemoryEnabled,
    request: Request,
    user=Depends(require_user),
    db=Depends(get_db),
):
    memory = owned_memory(db, memory_id, user.id)
    if data.enabled and (
        not memory.structured_rule or not (memory.rule_confirmed or data.confirmed)
    ):
        raise DomainError("MEMORY_CONFIRMATION_REQUIRED")
    if memory.structured_rule:
        MemoryRule.model_validate(memory.structured_rule)
    memory.rule_confirmed = memory.rule_confirmed or data.confirmed
    memory.rule_enabled = data.enabled
    db.flush()
    if memory.plant_id:
        plant = db.get(Plant, memory.plant_id)
        profile = db.scalar(
            select(CareProfile)
            .where(CareProfile.plant_id == plant.id, CareProfile.confirmed.is_(True))
            .order_by(CareProfile.version.desc())
            .limit(1)
        )
        if profile:
            issue_fallback(db, request.app.state.settings, plant, profile)
    return serialize(memory)
