from datetime import timedelta
import hashlib
import json
import math

from sqlalchemy import select, update, func

from flower.errors import DomainError
from flower.models import (
    Command,
    Device,
    DeviceStatus,
    Plant,
    CareProfile,
    WateringSession,
    Event,
    utcnow,
)
from flower.schemas import CalibrationInput, serialize

ACTIVE = ("pending", "claimed", "executing")


def quota_used(db, device_id, now):
    return float(
        db.scalar(
            select(func.coalesce(func.sum(WateringSession.quota_ml), 0)).where(
                WateringSession.device_id == device_id,
                WateringSession.occurred_at > now - timedelta(hours=24),
            )
        )
        or 0
    )


def safety_context(db, settings, device, plant, now, *, source):
    status = db.get(DeviceStatus, device.id)
    if (
        not status
        or not device.last_seen_at
        or (now - device.last_seen_at).total_seconds() > settings.device_offline_sec
    ):
        raise DomainError("DEVICE_OFFLINE")
    if (
        now - status.reported_at
    ).total_seconds() > settings.device_offline_sec or status.reported_at > now + timedelta(
        seconds=5
    ):
        raise DomainError("TELEMETRY_STALE")
    if device.operating_mode != "FULL" or status.operating_mode != "FULL":
        raise DomainError("SAFE_HOLD")
    if device.activity != "IDLE" or status.activity != "IDLE" or status.pump_commanded_on:
        raise DomainError("PUMP_BUSY")
    faults = (set(device.fault_codes) | set(status.fault_codes)) - {
        "BLE_STALE",
        "CAMERA_UNAVAILABLE",
    }
    if faults:
        raise DomainError(sorted(faults)[0])
    if not status.water_level_ok:
        raise DomainError("LOW_WATER", "储水桶水量不足，无法启动水泵")
    if status.soil_moisture is None or not math.isfinite(status.soil_moisture):
        raise DomainError("SOIL_SENSOR_FAULT")
    if not device.time_trusted:
        raise DomainError("TIME_UNTRUSTED")
    try:
        calibration = CalibrationInput.model_validate(device.calibration)
    except ValueError:
        raise DomainError("CALIBRATION_MISSING") from None
    profile = db.scalar(
        select(CareProfile)
        .where(CareProfile.plant_id == plant.id, CareProfile.confirmed.is_(True))
        .order_by(CareProfile.version.desc())
        .limit(1)
    )
    if not plant.recognition_confirmed or not profile:
        raise DomainError("PROFILE_MISSING")
    if profile.valid_until <= now:
        raise DomainError("PROFILE_STALE")
    if source == "cloud_auto" and not plant.auto_mode:
        raise DomainError("AUTO_MODE_DISABLED")
    return status, profile, calibration


def create_command(
    db,
    settings,
    *,
    device_id,
    plant_id,
    user_id,
    capability,
    action,
    parameters,
    source,
    run_mode,
    idempotency_key,
    policy_version=None,
    now=None,
):
    now = now or utcnow()
    if source not in {"cloud_auto", "user_manual"} or run_mode not in {
        "real",
        "demo",
        "offline_demo",
    }:
        raise DomainError("INVALID_COMMAND_SOURCE")
    if settings.app_env == "production" and run_mode != "real":
        raise DomainError("PRODUCTION_RUN_MODE")
    device = db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    plant = db.get(Plant, plant_id)
    if not device or not plant or plant.device_id != device_id or device.revoked:
        raise DomainError("NOT_FOUND", status=404)
    if user_id != device.owner_user_id or plant.user_id != user_id:
        raise DomainError("NOT_FOUND", status=404)
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "capability": capability,
                "action": action,
                "parameters": parameters,
                "source": source,
                "run_mode": run_mode,
                "plant_id": plant_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    key = hashlib.sha256(f"{device_id}:{user_id}:{idempotency_key}".encode()).hexdigest()
    previous = db.scalar(select(Command).where(Command.idempotency_key == key))
    if previous:
        if previous.request_hash != fingerprint:
            raise DomainError("IDEMPOTENCY_CONFLICT")
        return previous
    sweep_commands(db, now, device_id=device_id)
    if (capability, action) == ("camera", "capture"):
        if (
            source != "user_manual"
            or set(parameters) != {"shots"}
            or not set(parameters["shots"]) <= {"whole", "leaf", "flower"}
        ):
            raise DomainError("INVALID_CAPTURE")
        if db.scalar(
            select(Command.id).where(Command.device_id == device_id, Command.status.in_(ACTIVE))
        ):
            raise DomainError("DEVICE_BUSY")
        session_duration = 90
        execution_parameters = parameters
    elif (capability, action) == ("dispenser", "dispense"):
        status, profile, calibration = safety_context(
            db, settings, device, plant, now, source=source
        )
        if db.scalar(
            select(Command.id).where(
                Command.device_id == device_id,
                Command.action == "dispense",
                Command.status.in_(ACTIVE),
            )
        ):
            raise DomainError("ACTIVE_COMMAND")
        if set(parameters) - {"quantity", "unit", "pulse_ml", "stop_soil_pct"}:
            raise DomainError("INVALID_PARAMETERS")
        if source == "user_manual" and set(parameters) - {"quantity", "unit"}:
            raise DomainError("INVALID_PARAMETERS")
        quantity = float(parameters["quantity"])
        if parameters.get("unit") == "portion":
            if not quantity.is_integer():
                raise DomainError("INVALID_PORTION")
            quantity *= {"small": 10, "medium": 20, "large": 30}[plant.pot_size]
        elif parameters.get("unit") != "ml":
            raise DomainError("INVALID_UNIT")
        single_limit = settings.max_single_session_ml * (1 if plant.has_drainage else 0.5)
        if not math.isfinite(quantity) or not 0 < quantity <= single_limit:
            raise DomainError("SESSION_LIMIT")
        used = max(quota_used(db, device_id, now), status.used_24h_ml)
        if used + quantity > settings.pump_max_24h_ml:
            raise DomainError("QUOTA_EXCEEDED")
        last = db.scalar(
            select(func.max(WateringSession.occurred_at)).where(
                WateringSession.device_id == device_id, WateringSession.quota_ml > 0
            )
        )
        if last and (now - last).total_seconds() < settings.pump_min_interval_hours * 3600:
            raise DomainError("MIN_INTERVAL")
        # Portions are measured pulses, never a linear conversion from soil deficit.
        minimum = calibration.flow_ml_sec * calibration.min_run_sec + calibration.afterdrip_mean_ml
        preferred = parameters.get(
            "pulse_ml", {"small": 10, "medium": 20, "large": 30}[plant.pot_size]
        )
        if "pulse_ml" not in parameters:
            preferred *= 1 if plant.has_drainage else 0.5
        pulse = min(quantity, preferred)
        max_pulses = math.ceil(quantity / pulse)
        if max_pulses > settings.max_pulses_limit:
            raise DomainError("PULSE_LIMIT")
        for dose in [pulse, quantity - pulse * (max_pulses - 1)]:
            if dose < minimum:
                raise DomainError("BELOW_MINIMUM_DOSE")
            if (
                dose - calibration.afterdrip_mean_ml
            ) / calibration.flow_ml_sec > settings.pump_max_continuous_sec:
                raise DomainError("CONTINUOUS_LIMIT")
        absorb = (
            settings.soil_absorb_wait_sec if run_mode == "real" else settings.demo_absorb_wait_sec
        )
        wait = settings.pump_afterdrip_settle_sec + absorb
        session_duration = min(
            settings.session_max_duration_hard_sec,
            math.ceil(
                max_pulses * (settings.pump_max_continuous_sec + wait)
                + settings.session_safety_margin_sec
            ),
        )
        execution_parameters = {
            "target_ml": quantity,
            "pulse_ml": pulse,
            "max_pulses": max_pulses,
            "max_continuous_sec": settings.pump_max_continuous_sec,
            "afterdrip_settle_sec": settings.pump_afterdrip_settle_sec,
            "absorb_wait_sec": absorb,
            "wait_after_pulse_sec": wait,
            "stop_soil_pct": parameters.get(
                "stop_soil_pct", profile.profile["soil_target_min_pct"]
            ),
        }
    else:
        raise DomainError("UNSUPPORTED_CAPABILITY")
    cmd = Command(
        device_id=device_id,
        plant_id=plant_id,
        capability=capability,
        action=action,
        parameters=execution_parameters,
        source=source,
        run_mode=run_mode,
        source_type=device.source_type,
        policy_version=policy_version,
        created_by_user_id=user_id,
        created_at=now,
        idempotency_key=key,
        request_hash=fingerprint,
        claim_ttl_sec=settings.command_claim_ttl_sec,
        claim_deadline_at=now + timedelta(seconds=settings.command_claim_ttl_sec),
        start_grace_sec=settings.command_start_grace_sec,
        session_max_duration_sec=session_duration,
    )
    db.add(cmd)
    db.flush()
    if action == "dispense":
        db.add(
            WateringSession(
                command_id=cmd.id,
                device_id=device_id,
                plant_id=plant_id,
                source=source,
                source_type=device.source_type,
                reserved_ml=quantity,
                quota_ml=quantity,
                occurred_at=now,
            )
        )
    return cmd


def claim_command(db, device_id, now):
    sweep_commands(db, now, device_id=device_id)
    candidate = (
        select(Command.id)
        .where(
            Command.device_id == device_id,
            Command.status == "pending",
            Command.claim_deadline_at > now,
        )
        .order_by(Command.created_at)
        .limit(1)
    )
    if db.bind.dialect.name == "postgresql":
        candidate = candidate.with_for_update(skip_locked=True)
    cid = db.scalar(candidate)
    if cid is None:
        return None
    winner = db.scalar(
        update(Command)
        .where(Command.id == cid, Command.status == "pending", Command.claim_deadline_at > now)
        .values(status="claimed", claimed_at=now)
        .returning(Command)
    )
    return serialize(winner) if winner else None


def sweep_commands(db, now, device_id=None):
    query = select(Command).where(Command.status.in_(ACTIVE))
    if device_id:
        query = query.where(Command.device_id == device_id)
    for cmd in db.scalars(query.with_for_update(skip_locked=True)):
        expired = cmd.status == "pending" and cmd.claim_deadline_at <= now
        abandoned = (
            cmd.status == "claimed"
            and cmd.claimed_at + timedelta(seconds=cmd.start_grace_sec) <= now
        )
        timed_out = (
            cmd.status == "executing" and cmd.session_deadline_at and cmd.session_deadline_at <= now
        )
        if not (expired or abandoned or timed_out):
            continue
        cmd.status = "expired" if expired else "failed" if abandoned else "timed_out"
        cmd.finished_at = now
        cmd.result = {
            "reason": "claim_expired"
            if expired
            else "claim_abandoned"
            if abandoned
            else "session_timeout"
        }
        session = db.scalar(select(WateringSession).where(WateringSession.command_id == cmd.id))
        if session:
            session.status = "final" if expired or abandoned else "provisional"
            if expired or abandoned:
                session.quota_ml = 0
        db.add(
            Event(
                device_id=cmd.device_id,
                plant_id=cmd.plant_id,
                event_id=f"timeout:{cmd.id}",
                event_type=cmd.status,
                human_readable=cmd.result["reason"],
                source_type=cmd.source_type,
                occurred_at=now,
            )
        )
    db.flush()
