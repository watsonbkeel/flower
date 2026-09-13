from datetime import timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from flower.auth import get_db, require_user, owned_plant
from flower.models import Telemetry, WateringSession, utcnow
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
    coverage_start = rows[0].occurred_at.isoformat() if rows else None
    coverage = (rows[-1].occurred_at - rows[0].occurred_at).total_seconds() / 3600 if rows else 0
    step = max(1, len(rows) // 600)
    sampled = rows[::step]
    if rows and sampled[-1] is not rows[-1]:
        sampled.append(rows[-1])
    water = db.scalars(
        select(WateringSession)
        .where(
            WateringSession.plant_id == plant.id,
            WateringSession.source_type == source_type,
            WateringSession.occurred_at >= start,
            WateringSession.actual_ml > 0,
        )
        .order_by(WateringSession.occurred_at)
    )
    return {
        "source_type": source_type,
        "coverage_start": coverage_start,
        "coverage_hours": round(coverage, 2),
        "requested_range": range,
        "points": [serialize(r) for r in sampled],
        "watering_events": [serialize(w) for w in water],
    }
