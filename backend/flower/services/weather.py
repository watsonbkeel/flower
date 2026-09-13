from sqlalchemy import select

from flower.errors import DomainError
from flower.models import CareProfile, Device, Job, Plant
from flower.services.jobs import enqueue_job
from flower.services.knowledge import Weather


def current_weather(value, now, source_type):
    try:
        weather = Weather.model_validate(value)
    except ValueError:
        return None
    if weather.source_type != source_type or not weather.observed_at <= now < weather.valid_until:
        return None
    return weather


def weather_context(db, profile, now):
    if not profile or not profile.confirmed or profile.valid_until <= now:
        raise DomainError("PROFILE_STALE")
    plant = db.get(Plant, profile.plant_id)
    device = db.get(Device, plant.device_id)
    latest = db.scalar(
        select(CareProfile.id)
        .where(CareProfile.plant_id == plant.id, CareProfile.confirmed.is_(True))
        .order_by(CareProfile.version.desc())
        .limit(1)
    )
    if latest != profile.id or not plant.recognition_confirmed or device.revoked:
        raise DomainError("PROFILE_STALE")
    return {
        "city": plant.city,
        "latitude": plant.latitude,
        "longitude": plant.longitude,
        "source_type": device.source_type,
    }


def schedule_weather(db, now):
    for profile in db.scalars(
        select(CareProfile).where(CareProfile.confirmed.is_(True), CareProfile.valid_until > now)
    ):
        try:
            context = weather_context(db, profile, now)
        except DomainError:
            continue
        if current_weather(profile.profile.get("weather"), now, context["source_type"]):
            continue
        if db.scalar(
            select(Job.id)
            .where(
                Job.job_type == "weather_refresh",
                Job.target_id == profile.id,
                Job.status.in_(["queued", "running"]),
            )
            .limit(1)
        ):
            continue
        enqueue_job(
            db,
            "weather_refresh",
            "care_profile",
            profile.id,
            db.get(Plant, profile.plant_id).user_id,
            f"weather:{profile.id}:{now.replace(minute=0, second=0, microsecond=0).isoformat()}",
        )
