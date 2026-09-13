from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from flower.auth import get_db, require_device, issue_token, verify_secret
from flower.errors import DomainError
from flower.models import (
    Device,
    DeviceStatus,
    Telemetry,
    Plant,
    Command,
    WateringSession,
    Event,
    FallbackPolicy,
    utcnow,
)
from flower.schemas import (
    DeviceLogin,
    TelemetryInput,
    ProgressInput,
    ResultInput,
    CalibrationInput,
    EventBatch,
    QuotaInput,
    serialize,
)
from flower.services.commands import claim_command, quota_used
from flower.services.alerts import alert

router = APIRouter(prefix="/api/v1/device")


@router.post("/auth/token")
def login(data: DeviceLogin, request: Request, db=Depends(get_db)):
    device = db.scalar(select(Device).where(Device.device_code == data.device_code))
    if (
        device is None
        or device.revoked
        or not verify_secret(data.device_secret, device.secret_hash)
    ):
        raise DomainError("DEVICE_AUTH_FAILED", status=401)
    return {
        "access_token": issue_token(
            request.app.state.settings, device.id, "device", device.token_version
        ),
        "token_type": "bearer",
        "expires_in": 1800,
        "device_id": device.id,
        "spec_version": "2.2.2",
    }


@router.post("/telemetry")
def telemetry(data: TelemetryInput, device=Depends(require_device), db=Depends(get_db)):
    now = utcnow()
    db.refresh(device, with_for_update=True)
    if data.source_type != device.source_type:
        raise DomainError("SOURCE_TYPE_MISMATCH")
    if data.occurred_at > now + timedelta(seconds=5):
        raise DomainError("FUTURE_TELEMETRY")
    exists = db.scalar(
        select(Telemetry.id).where(
            Telemetry.device_id == device.id, Telemetry.event_id == data.event_id
        )
    )
    if exists:
        return {"accepted": True, "duplicate": True}
    plant_id = db.scalar(
        select(Plant.id).where(Plant.device_id == device.id, Plant.is_primary.is_(True))
    )
    fields = data.model_dump(
        include={
            "event_id",
            "soil_moisture",
            "soil_raw",
            "temperature_c",
            "air_humidity",
            "water_level_ok",
            "source_type",
            "occurred_at",
        }
    )
    db.add(
        Telemetry(
            device_id=device.id,
            plant_id=plant_id,
            **fields,
            extra_data=data.model_dump(mode="json", exclude=set(fields)),
        )
    )
    status = db.get(DeviceStatus, device.id)
    if status is None or data.occurred_at > status.reported_at:
        status_fields = data.model_dump(
            include={
                "operating_mode",
                "activity",
                "fault_codes",
                "soil_moisture",
                "soil_raw",
                "temperature_c",
                "air_humidity",
                "water_level_ok",
                "pump_commanded_on",
                "used_24h_ml",
                "sensor_health",
                "source_type",
            }
        )
        if status is None:
            status = DeviceStatus(
                device_id=device.id, reported_at=data.occurred_at, **status_fields
            )
            db.add(status)
        else:
            for key, value in status_fields.items():
                setattr(status, key, value)
            status.reported_at = data.occurred_at
        device.operating_mode, device.activity = data.operating_mode, data.activity
        device.fault_codes, device.time_trusted = data.fault_codes, data.time_trusted
        device.firmware_version = data.firmware_version
        for code in data.fault_codes:
            alert(db, device, code, f"设备报告 {code}", plant_id=plant_id)
        if not data.water_level_ok:
            alert(db, device, "LOW_WATER", "储水桶缺水，补水已停止", plant_id=plant_id)
    device.last_seen_at = now
    return {"accepted": True, "duplicate": False, "spec_version": "2.2.2"}


@router.post("/commands/claim")
def claim(device=Depends(require_device), db=Depends(get_db)):
    return {"command": claim_command(db, device.id, utcnow())}


def device_command(db, device, command_id):
    cmd = db.scalar(
        select(Command)
        .where(Command.id == str(command_id), Command.device_id == device.id)
        .with_for_update()
    )
    if not cmd:
        raise DomainError("NOT_FOUND", status=404)
    return cmd


@router.post("/commands/{command_id}/started")
def started(command_id: UUID, device=Depends(require_device), db=Depends(get_db)):
    now = utcnow()
    cmd = device_command(db, device, command_id)
    if cmd.status == "executing":
        return serialize(cmd)
    if cmd.status != "claimed" or cmd.claimed_at + timedelta(seconds=cmd.start_grace_sec) <= now:
        raise DomainError("COMMAND_NOT_STARTABLE")
    cmd.status, cmd.started_at = "executing", now
    cmd.session_deadline_at = now + timedelta(seconds=cmd.session_max_duration_sec)
    session = db.scalar(select(WateringSession).where(WateringSession.command_id == cmd.id))
    if session:
        session.occurred_at = now
    db.flush()
    return serialize(cmd)


@router.post("/commands/{command_id}/progress")
def progress(
    command_id: UUID, data: ProgressInput, device=Depends(require_device), db=Depends(get_db)
):
    cmd = device_command(db, device, command_id)
    now = utcnow()
    if cmd.status != "executing" or cmd.session_deadline_at <= now:
        raise DomainError("COMMAND_NOT_EXECUTING")
    if len(data.pulses) > cmd.parameters.get("max_pulses", 3) or sum(
        p.estimated_ml for p in data.pulses
    ) > cmd.parameters.get("target_ml", 0):
        raise DomainError("INVALID_PROGRESS")
    previous = (cmd.result or {}).get("pulses", [])
    payload = data.model_dump(mode="json")
    if payload["pulses"][: len(previous)] != previous:
        raise DomainError("PROGRESS_ROLLBACK")
    cmd.last_progress_at = now
    cmd.result = payload
    session = db.scalar(select(WateringSession).where(WateringSession.command_id == cmd.id))
    if session:
        session.pulse_details = payload["pulses"]
    return serialize(cmd)


@router.post("/commands/{command_id}/result")
def result(command_id: UUID, data: ResultInput, device=Depends(require_device), db=Depends(get_db)):
    cmd = device_command(db, device, command_id)
    payload = data.model_dump(mode="json")
    if cmd.status not in {"claimed", "executing"}:
        if cmd.result == payload:
            return serialize(cmd)
        raise DomainError("RESULT_CONFLICT")
    if data.status == "succeeded" and cmd.status != "executing":
        raise DomainError("RESULT_BEFORE_STARTED")
    if cmd.action == "dispense" and data.actual_ml > cmd.parameters["target_ml"]:
        raise DomainError("INVALID_SETTLEMENT")
    now = utcnow()
    if cmd.action == "dispense" and data.status == "succeeded":
        expected = list(range(1, len(data.pulses) + 1))
        previous_total = sum(p["estimated_ml"] for p in (cmd.result or {}).get("pulses", []))
        if (
            data.provisional
            or [p.pulse for p in data.pulses] != expected
            or len(data.pulses) > cmd.parameters["max_pulses"]
            or abs(sum(p.estimated_ml for p in data.pulses) - data.actual_ml) > 0.001
            or data.actual_ml < previous_total
            or any(p.finished_at < cmd.started_at or p.finished_at > now for p in data.pulses)
        ):
            raise DomainError("UNVERIFIED_SETTLEMENT")
    if cmd.session_deadline_at and now >= cmd.session_deadline_at and data.status == "succeeded":
        raise DomainError("SESSION_TIMEOUT")
    cmd.status, cmd.result, cmd.finished_at = data.status, payload, now
    session = db.scalar(select(WateringSession).where(WateringSession.command_id == cmd.id))
    if session:
        session.actual_ml = data.actual_ml
        session.status = (
            "provisional" if data.provisional or data.status != "succeeded" else "final"
        )
        session.quota_ml = (
            session.reserved_ml if session.status == "provisional" else data.actual_ml
        )
        session.pulse_details = payload["pulses"]
    db.add(
        Event(
            device_id=device.id,
            plant_id=cmd.plant_id,
            event_id=f"result:{cmd.id}",
            event_type=f"command_{cmd.status}",
            event_data={"command_id": cmd.id, **payload},
            human_readable="补水完成"
            if cmd.action == "dispense" and cmd.status == "succeeded"
            else f"指令 {cmd.status}",
            source_type=cmd.source_type,
            occurred_at=now,
        )
    )
    if cmd.status != "succeeded":
        alert(
            db,
            device,
            "WATERING_FAILED" if cmd.action == "dispense" else "CAPTURE_FAILED",
            data.reason or cmd.status,
            plant_id=cmd.plant_id,
        )
    return serialize(cmd)


@router.post("/events/batch")
def events(data: EventBatch, device=Depends(require_device), db=Depends(get_db)):
    db.refresh(device, with_for_update=True)
    plant_id = db.scalar(
        select(Plant.id).where(Plant.device_id == device.id, Plant.is_primary.is_(True))
    )
    accepted = []
    for item in data.events:
        if item.source_type != device.source_type:
            raise DomainError("SOURCE_TYPE_MISMATCH")
        if not db.scalar(
            select(Event.id).where(Event.device_id == device.id, Event.event_id == item.event_id)
        ):
            db.add(Event(device_id=device.id, plant_id=plant_id, **item.model_dump()))
        accepted.append(item.event_id)
    return {"accepted": accepted}


@router.post("/calibration")
def calibration(data: CalibrationInput, device=Depends(require_device), db=Depends(get_db)):
    device.calibration = data.model_dump(mode="json")
    return {"accepted": True, "spec_version": "2.2.2"}


@router.get("/fallback-policy")
def fallback(device=Depends(require_device), db=Depends(get_db)):
    policy = db.scalar(
        select(FallbackPolicy)
        .where(FallbackPolicy.device_id == device.id, FallbackPolicy.valid_until > utcnow())
        .order_by(FallbackPolicy.policy_version.desc())
        .limit(1)
    )
    if not policy:
        raise DomainError("POLICY_MISSING", status=404)
    return {"policy": policy.policy, "policy_hash": policy.policy_hash}


@router.post("/quota/reconcile")
def reconcile(data: QuotaInput, device=Depends(require_device), db=Depends(get_db)):
    db.refresh(device, with_for_update=True)
    cloud_used = quota_used(db, device.id, utcnow())
    divergence = abs(cloud_used - data.used_24h_ml) > 0.01
    if divergence:
        alert(db, device, "QUOTA_DIVERGENCE", "本地与云端额度记录不同，暂取较保守值")
    status = db.get(DeviceStatus, device.id)
    if status:
        status.used_24h_ml = max(status.used_24h_ml, data.used_24h_ml)
    return {
        "verified_cloud_used": cloud_used,
        "effective_used": max(cloud_used, data.used_24h_ml),
        "divergence": divergence,
        "observed_at": utcnow().isoformat(),
    }
