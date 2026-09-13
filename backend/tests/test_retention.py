from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, func

from flower.models import Telemetry, TelemetryHourly, utcnow


def seed_rows(system, age_days=31):
    now = utcnow().replace(minute=0, second=0, microsecond=0)
    with system["app"].state.sessions.begin() as db:
        for source, values in [("real", [20, 40]), ("mock", [90])]:
            for index, value in enumerate(values):
                db.add(
                    Telemetry(
                        device_id=system["device_id"],
                        plant_id=system["plant_id"],
                        event_id=str(uuid4()),
                        source_type=source,
                        soil_moisture=value,
                        water_level_ok=True,
                        occurred_at=now - timedelta(days=age_days) + timedelta(minutes=index),
                    )
                )
    return now


def test_aggregation_idempotent_separates_sources_and_cleanup_checks_values(system):
    from flower.services.retention import aggregate, cleanup

    now = seed_rows(system)
    with system["app"].state.sessions.begin() as db:
        assert cleanup(db, system["settings"], now)["raw"] == 0
        aggregate(db, now)
        aggregate(db, now)
        buckets = list(db.scalars(select(TelemetryHourly).order_by(TelemetryHourly.source_type)))
        assert len(buckets) == 2
        assert [b.soil_avg for b in buckets] == [90, 30]
        buckets[1].soil_avg = 99
        db.flush()
        assert cleanup(db, system["settings"], now)["raw"] == 1
        assert db.scalar(select(func.count()).select_from(Telemetry)) == 2
        aggregate(db, now)
        assert cleanup(db, system["settings"], now)["raw"] == 2
        assert db.scalar(select(func.count()).select_from(TelemetryHourly)) == 2


def test_open_hour_and_retained_raw_never_removed(system):
    from flower.services.retention import aggregate, cleanup

    now = seed_rows(system, 0) + timedelta(minutes=10)
    with system["app"].state.sessions.begin() as db:
        aggregate(db, now)
        assert db.scalar(select(func.count()).select_from(TelemetryHourly)) == 0
        assert cleanup(db, system["settings"], now)["raw"] == 0


def test_trend_coverage_does_not_count_missing_days(system):
    now = seed_rows(system, 6)
    with system["app"].state.sessions.begin() as db:
        db.add(
            Telemetry(
                device_id=system["device_id"],
                plant_id=system["plant_id"],
                event_id=str(uuid4()),
                source_type="real",
                soil_moisture=50,
                water_level_ok=True,
                occurred_at=now - timedelta(hours=1),
            )
        )
    response = system["client"].get(
        f"/api/v1/plants/{system['plant_id']}/telemetry/series?range=7d&source_type=real",
        headers=system["user_headers"],
    )
    assert response.status_code == 200
    assert response.json()["coverage_hours"] < 3
    assert response.json()["sample_count"] == 3


def test_cleanup_preserves_pinned_images_active_jobs_and_referenced_commands(system):
    from flower.models import PlantImage, Memory, Job
    from flower.services.retention import cleanup, schedule

    now = utcnow()
    with system["app"].state.sessions.begin() as db:
        for index in range(3):
            image = PlantImage(
                device_id=system["device_id"],
                plant_id=system["plant_id"],
                file_path=f"2026/01/{index}.jpg",
                image_type="memory",
                source_type="mock",
                expires_at=now - timedelta(days=1),
            )
            db.add(image)
            db.flush()
            if index == 0:
                db.add(
                    Memory(user_id=system["user_id"], title="Pinned", photo_path=image.file_path)
                )
            if index == 1:
                db.add(
                    Job(
                        job_type="plant_recognition",
                        target_type="image",
                        target_id=image.id,
                        idempotency_key="active-image",
                        status="queued",
                    )
                )
        db.flush()
        assert cleanup(db, system["settings"], now)["images"] == 1
        schedule(db, now)
        schedule(db, now)
        assert db.scalar(select(func.count()).select_from(Job)) == 3
        assert db.scalar(select(func.count()).select_from(PlantImage)) == 2
