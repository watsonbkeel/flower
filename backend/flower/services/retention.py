"""Completed-hour aggregation and independently checked retention."""

from collections import defaultdict
from datetime import timedelta
import math

from sqlalchemy import select, delete, exists

from flower.models import (
    Telemetry,
    TelemetryHourly,
    PlantImage,
    Plant,
    Memory,
    Job,
    Command,
    WateringSession,
)


def hour(value):
    return value.replace(minute=0, second=0, microsecond=0)


def groups(db, before):
    grouped = defaultdict(list)
    for row in db.scalars(
        select(Telemetry).where(Telemetry.occurred_at < before).order_by(Telemetry.occurred_at)
    ):
        grouped[(row.device_id, row.plant_id, hour(row.occurred_at), row.source_type)].append(row)
    return grouped


def statistics(rows):
    def values(field):
        return [getattr(row, field) for row in rows if getattr(row, field) is not None]

    def avg(field):
        items = values(field)
        return sum(items) / len(items) if items else None

    soil = values("soil_moisture")
    return dict(
        soil_avg=avg("soil_moisture"),
        soil_min=min(soil) if soil else None,
        soil_max=max(soil) if soil else None,
        temperature_avg=avg("temperature_c"),
        air_humidity_avg=avg("air_humidity"),
        water_level_ok_ratio=avg("water_level_ok"),
        sample_count=len(rows),
        coverage_seconds=sum(
            min(30, max(0, (b.occurred_at - a.occurred_at).total_seconds()))
            for a, b in zip(rows, rows[1:])
        ),
    )


def bucket_for(db, key):
    return db.scalar(
        select(TelemetryHourly)
        .where(
            TelemetryHourly.device_id == key[0],
            TelemetryHourly.plant_id == key[1],
            TelemetryHourly.bucket_start == key[2],
            TelemetryHourly.source_type == key[3],
        )
        .with_for_update()
    )


def matches(bucket, expected):
    return all(
        (getattr(bucket, name) is None and value is None)
        or (
            getattr(bucket, name) is not None
            and value is not None
            and math.isclose(getattr(bucket, name), value, rel_tol=1e-10, abs_tol=1e-10)
        )
        for name, value in expected.items()
    )


def aggregate(db, now):
    count = 0
    for key, rows in groups(db, hour(now)).items():
        bucket = bucket_for(db, key)
        # Late uploads after raw purge are retained for manual reconciliation.
        if bucket and bucket.raw_purged:
            continue
        if not bucket:
            bucket = TelemetryHourly(
                device_id=key[0], plant_id=key[1], bucket_start=key[2], source_type=key[3]
            )
            db.add(bucket)
        expected = statistics(rows)
        for name, value in expected.items():
            setattr(bucket, name, value)
        bucket.verified = False
        db.flush()
        db.refresh(bucket)
        bucket.verified = matches(bucket, expected)
        count += 1
    db.flush()
    return {"buckets": count}


def cleanup(db, settings, now):
    result = dict(raw=0, hourly=0, images=0, jobs=0, commands=0)
    # Unreferenced files get a grace period; rollback can never lose a live image.
    referenced = set(db.scalars(select(PlantImage.file_path)))
    for path in settings.upload_dir.glob("*/*/*.jpg"):
        if path.is_symlink():
            continue
        relative = path.relative_to(settings.upload_dir).as_posix()
        if (
            relative not in referenced
            and path.stat().st_mtime < (now - timedelta(days=1)).timestamp()
        ):
            path.unlink(missing_ok=True)
    cutoff = hour(now - timedelta(days=settings.telemetry_raw_retention_days))
    for key, rows in groups(db, cutoff).items():
        bucket = bucket_for(db, key)
        if (
            bucket
            and bucket.verified
            and not bucket.raw_purged
            and matches(bucket, statistics(rows))
        ):
            db.execute(delete(Telemetry).where(Telemetry.id.in_([r.id for r in rows])))
            bucket.raw_purged = True
            result["raw"] += len(rows)
    result["hourly"] = db.execute(
        delete(TelemetryHourly).where(
            TelemetryHourly.bucket_start
            < now - timedelta(days=settings.telemetry_hourly_retention_days),
            TelemetryHourly.raw_purged.is_(True),
        )
    ).rowcount
    for image in db.scalars(select(PlantImage).where(PlantImage.expires_at < now)):
        pinned = db.scalar(
            select(Plant.id).where(Plant.photo_path == image.file_path).limit(1)
        ) or db.scalar(select(Memory.id).where(Memory.photo_path == image.file_path).limit(1))
        active = db.scalar(
            select(Job.id)
            .where(Job.target_id == image.id, Job.status.in_(["queued", "running"]))
            .limit(1)
        )
        if pinned or active:
            continue
        db.delete(image)
        result["images"] += 1
    cutoff = now - timedelta(days=90)
    result["jobs"] = db.execute(
        delete(Job).where(Job.status.in_(["succeeded", "failed"]), Job.finished_at < cutoff)
    ).rowcount
    # Audit sessions retain command references; never delete their parent command.
    result["commands"] = db.execute(
        delete(Command).where(
            Command.status.in_(["succeeded", "failed", "expired", "timed_out", "cancelled"]),
            Command.finished_at < cutoff,
            ~exists(select(WateringSession.id).where(WateringSession.command_id == Command.id)),
        )
    ).rowcount
    return result


def schedule(db, now):
    from flower.services.jobs import enqueue_job

    for kind in ["trend_aggregation", "cleanup"]:
        enqueue_job(
            db,
            kind,
            "system",
            "00000000-0000-0000-0000-000000000000",
            None,
            f"{kind}:{hour(now).isoformat()}",
        )
