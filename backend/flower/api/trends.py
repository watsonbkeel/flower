from datetime import timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from flower.auth import get_db, require_user, owned_plant
from flower.models import Telemetry, TelemetryHourly, WateringSession, utcnow
from flower.schemas import SourceType, serialize

router = APIRouter(prefix="/api/v1")


@router.get("/plants/{plant_id}/telemetry/series")
def series(
    plant_id: UUID,
    range: Literal["1d", "7d", "30d"] = Query("7d"),
    source_type: SourceType = "real",
    user=Depends(require_user),
    db=Depends(get_db),
):
    plant = owned_plant(db, str(plant_id), user.id)
    now = utcnow()
    start = now - timedelta(days={"1d": 1, "7d": 7, "30d": 30}[range])
    rows = list(
        db.scalars(
            select(Telemetry)
            .where(
                Telemetry.plant_id == plant.id,
                Telemetry.source_type == source_type,
                Telemetry.occurred_at >= start,
                Telemetry.occurred_at <= now,
            )
            .order_by(Telemetry.occurred_at)
        )
    )
    from flower.services.retention import hour

    hourly = list(
        db.scalars(
            select(TelemetryHourly)
            .where(
                TelemetryHourly.plant_id == plant.id,
                TelemetryHourly.source_type == source_type,
                TelemetryHourly.bucket_start >= start,
                TelemetryHourly.bucket_start <= now,
                TelemetryHourly.verified.is_(True),
            )
            .order_by(TelemetryHourly.bucket_start)
        )
    )
    raw_hours = {hour(row.occurred_at) for row in rows}
    historical = [bucket for bucket in hourly if bucket.bucket_start not in raw_hours]
    # Coverage is sampled duration, with gaps capped at the device cadence.
    coverage = (
        sum(
            min(30, max(0, (b.occurred_at - a.occurred_at).total_seconds()))
            for a, b in zip(rows, rows[1:])
        )
        / 3600
    )
    coverage += sum(b.coverage_seconds / 3600 for b in historical)
    points = [serialize(row) for row in rows]
    points += [
        dict(
            occurred_at=b.bucket_start.isoformat(),
            soil_moisture=b.soil_avg,
            source_type=b.source_type,
            sample_count=b.sample_count,
            resolution="hourly",
        )
        for b in historical
    ]
    points.sort(key=lambda p: p["occurred_at"])
    coverage_start = points[0]["occurred_at"] if points else None
    # Hourly values preserve bucket gaps without joining unrelated raw samples.
    if range != "1d" and hourly:
        present = {b.bucket_start for b in hourly}
        points = [serialize(r) for r in rows if hour(r.occurred_at) not in present]
        points += [
            dict(
                occurred_at=b.bucket_start.isoformat(),
                soil_moisture=b.soil_avg,
                source_type=b.source_type,
                sample_count=b.sample_count,
                resolution="hourly",
            )
            for b in hourly
        ]
        points.sort(key=lambda p: p["occurred_at"])
    water = db.scalars(
        select(WateringSession)
        .where(
            WateringSession.plant_id == plant.id,
            WateringSession.source_type == source_type,
            WateringSession.occurred_at >= start,
            WateringSession.occurred_at <= now,
            WateringSession.actual_ml > 0,
        )
        .order_by(WateringSession.occurred_at)
    )
    return {
        "source_type": source_type,
        "coverage_start": coverage_start,
        "coverage_hours": round(coverage, 2),
        "requested_range": range,
        "sample_count": len(rows) + sum(b.sample_count for b in historical),
        "points": points,
        "watering_events": [serialize(w) for w in water],
    }
