from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    String,
    DateTime,
    Float,
    Boolean,
    Integer,
    JSON,
    Text,
    Uuid,
    ForeignKey,
    Index,
    CheckConstraint,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from flower.db import Base


class SchemaInfo(Base):
    __tablename__ = "schema_info"
    spec_version: Mapped[str] = mapped_column(String, primary_key=True)


def utcnow():
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            raise ValueError("timezone aware datetime required")
        return value.astimezone(timezone.utc) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )


JSON_DATA = JSON().with_variant(JSONB(), "postgresql")


class Record:
    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class User(Record, Base):
    __tablename__ = "users"
    openid: Mapped[str] = mapped_column(String, unique=True)
    nickname: Mapped[str | None] = mapped_column(String)


class Device(Record, Base):
    __tablename__ = "devices"
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    device_code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String, default="Flower")
    scene_type: Mapped[str] = mapped_column(String, default="plant_care")
    secret_hash: Mapped[str] = mapped_column(String)
    token_version: Mapped[int] = mapped_column(Integer, default=1)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    operating_mode: Mapped[str] = mapped_column(String, default="STARTING")
    activity: Mapped[str] = mapped_column(String, default="IDLE")
    fault_codes: Mapped[list] = mapped_column(JSON_DATA, default=list)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    firmware_version: Mapped[str] = mapped_column(String, default="unknown")
    spec_version: Mapped[str] = mapped_column(String, default="2.2.2")
    time_trusted: Mapped[bool] = mapped_column(Boolean, default=False)
    calibration: Mapped[dict] = mapped_column(JSON_DATA, default=dict)
    config: Mapped[dict] = mapped_column(JSON_DATA, default=dict)
    source_type: Mapped[str] = mapped_column(String, default="mock")
    __table_args__ = (
        CheckConstraint(
            "operating_mode IN ('STARTING','FULL','LOCAL_CONSERVATIVE','SAFE_HOLD')",
            name="ck_device_mode",
        ),
        CheckConstraint(
            "source_type IN ('real','demo','imported_test','mock')", name="ck_device_source"
        ),
    )


class Plant(Record, Base):
    __tablename__ = "plants"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    name: Mapped[str] = mapped_column(String)
    common_name: Mapped[str | None] = mapped_column(String)
    scientific_name: Mapped[str | None] = mapped_column(String)
    input_method: Mapped[str | None] = mapped_column(String)
    recognition_confidence: Mapped[float | None] = mapped_column(Float)
    recognition_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    placement_type: Mapped[str] = mapped_column(String, default="indoor")
    city: Mapped[str] = mapped_column(String, default="")
    timezone: Mapped[str] = mapped_column(String, default="Asia/Shanghai")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    pot_size: Mapped[str] = mapped_column(String, default="small")
    pot_diameter_cm: Mapped[float | None] = mapped_column(Float)
    pot_material: Mapped[str] = mapped_column(String, default="plastic")
    has_drainage: Mapped[bool] = mapped_column(Boolean, default=False)
    photo_path: Mapped[str | None] = mapped_column(String)
    auto_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_mode_since: Mapped[datetime | None] = mapped_column(UTCDateTime)
    __table_args__ = (
        Index(
            "idx_device_primary_plant",
            "device_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
            sqlite_where=text("is_primary = 1"),
        ),
    )


class CareProfile(Record, Base):
    __tablename__ = "care_profiles"
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"))
    version: Mapped[int] = mapped_column(Integer)
    profile: Mapped[dict] = mapped_column(JSON_DATA)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    valid_until: Mapped[datetime] = mapped_column(UTCDateTime)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    source_conflict: Mapped[dict | None] = mapped_column(JSON_DATA)
    __table_args__ = (UniqueConstraint("plant_id", "version"),)


class FallbackPolicy(Record, Base):
    __tablename__ = "fallback_policies"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"))
    policy_version: Mapped[int] = mapped_column(Integer)
    profile_version: Mapped[int] = mapped_column(Integer)
    policy: Mapped[dict] = mapped_column(JSON_DATA)
    policy_hash: Mapped[str] = mapped_column(String)
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime)
    valid_until: Mapped[datetime] = mapped_column(UTCDateTime)
    __table_args__ = (UniqueConstraint("device_id", "policy_version"),)


class DeviceStatus(Base):
    __tablename__ = "device_status"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), primary_key=True)
    operating_mode: Mapped[str] = mapped_column(String)
    activity: Mapped[str] = mapped_column(String)
    fault_codes: Mapped[list] = mapped_column(JSON_DATA, default=list)
    soil_moisture: Mapped[float | None] = mapped_column(Float)
    soil_raw: Mapped[float | None] = mapped_column(Float)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    air_humidity: Mapped[float | None] = mapped_column(Float)
    water_level_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    pump_commanded_on: Mapped[bool] = mapped_column(Boolean, default=False)
    used_24h_ml: Mapped[float] = mapped_column(Float, default=0)
    sensor_health: Mapped[dict] = mapped_column(JSON_DATA, default=dict)
    reported_at: Mapped[datetime] = mapped_column(UTCDateTime)
    source_type: Mapped[str] = mapped_column(String)


class Telemetry(Record, Base):
    __tablename__ = "telemetry"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"))
    event_id: Mapped[str] = mapped_column(String)
    soil_moisture: Mapped[float | None] = mapped_column(Float)
    soil_raw: Mapped[float | None] = mapped_column(Float)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    air_humidity: Mapped[float | None] = mapped_column(Float)
    water_level_ok: Mapped[bool] = mapped_column(Boolean)
    source_type: Mapped[str] = mapped_column(String)
    extra_data: Mapped[dict] = mapped_column(JSON_DATA, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    __table_args__ = (
        UniqueConstraint("device_id", "event_id"),
        Index("idx_telemetry_device_occurred", "device_id", "occurred_at"),
    )


class TelemetryHourly(Record, Base):
    __tablename__ = "telemetry_hourly"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"))
    bucket_start: Mapped[datetime] = mapped_column(UTCDateTime)
    source_type: Mapped[str] = mapped_column(String)
    soil_avg: Mapped[float | None] = mapped_column(Float)
    soil_min: Mapped[float | None] = mapped_column(Float)
    soil_max: Mapped[float | None] = mapped_column(Float)
    temperature_avg: Mapped[float | None] = mapped_column(Float)
    air_humidity_avg: Mapped[float | None] = mapped_column(Float)
    water_level_ok_ratio: Mapped[float | None] = mapped_column(Float)
    sample_count: Mapped[int] = mapped_column(Integer)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("device_id", "bucket_start", "source_type"),)


class Command(Record, Base):
    __tablename__ = "commands"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"))
    capability: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    parameters: Mapped[dict] = mapped_column(JSON_DATA)
    status: Mapped[str] = mapped_column(String, default="pending")
    source: Mapped[str] = mapped_column(String)
    run_mode: Mapped[str] = mapped_column(String)
    source_type: Mapped[str] = mapped_column(String)
    policy_version: Mapped[int | None] = mapped_column(Integer)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    request_hash: Mapped[str] = mapped_column(String)
    claim_ttl_sec: Mapped[int] = mapped_column(Integer)
    claim_deadline_at: Mapped[datetime] = mapped_column(UTCDateTime)
    claimed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    start_grace_sec: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    session_max_duration_sec: Mapped[int] = mapped_column(Integer)
    session_deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_progress_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    result: Mapped[dict | None] = mapped_column(JSON_DATA)
    __table_args__ = (
        CheckConstraint("source IN ('cloud_auto','user_manual')", name="ck_command_source"),
        CheckConstraint("run_mode IN ('real','demo','offline_demo')", name="ck_command_run_mode"),
        CheckConstraint(
            "status IN ('pending','claimed','executing','succeeded','failed','expired','timed_out','cancelled')",
            name="ck_command_status",
        ),
        Index(
            "idx_device_active_dispense",
            "device_id",
            unique=True,
            postgresql_where=text(
                "action = 'dispense' AND status IN ('pending','claimed','executing')"
            ),
            sqlite_where=text(
                "action = 'dispense' AND status IN ('pending','claimed','executing')"
            ),
        ),
    )


class WateringSession(Record, Base):
    __tablename__ = "watering_sessions"
    command_id: Mapped[str | None] = mapped_column(ForeignKey("commands.id"), unique=True)
    local_id: Mapped[str | None] = mapped_column(String, unique=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"))
    source: Mapped[str] = mapped_column(String)
    source_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="reserved")
    reserved_ml: Mapped[float] = mapped_column(Float)
    actual_ml: Mapped[float | None] = mapped_column(Float)
    quota_ml: Mapped[float] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    pulse_details: Mapped[list] = mapped_column(JSON_DATA, default=list)


class Event(Record, Base):
    __tablename__ = "events"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"))
    event_id: Mapped[str] = mapped_column(String)
    event_type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, default="info")
    event_data: Mapped[dict] = mapped_column(JSON_DATA, default=dict)
    human_readable: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    __table_args__ = (UniqueConstraint("device_id", "event_id"),)


class Memory(Record, Base):
    __tablename__ = "memories"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"))
    title: Mapped[str] = mapped_column(String)
    story: Mapped[str] = mapped_column(Text, default="")
    original_experience: Mapped[str] = mapped_column(Text, default="")
    structured_rule: Mapped[dict | None] = mapped_column(JSON_DATA)
    rule_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_count: Mapped[int] = mapped_column(Integer, default=0)
    last_applied_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    photo_path: Mapped[str | None] = mapped_column(String)


class PlantImage(Record, Base):
    __tablename__ = "plant_images"
    plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"))
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    file_path: Mapped[str] = mapped_column(String, unique=True)
    image_type: Mapped[str] = mapped_column(String)
    quality_flags: Mapped[list] = mapped_column(JSON_DATA, default=list)
    recognition_result: Mapped[dict | None] = mapped_column(JSON_DATA)
    source_type: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Job(Record, Base):
    __tablename__ = "jobs"
    job_type: Mapped[str] = mapped_column(String)
    target_type: Mapped[str] = mapped_column(String)
    target_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="queued")
    progress_stage: Mapped[str] = mapped_column(String, default="queued")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    timeout_sec: Mapped[int] = mapped_column(Integer, default=90)
    locked_by: Mapped[str | None] = mapped_column(String)
    locked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    result: Mapped[dict | None] = mapped_column(JSON_DATA)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed')", name="ck_job_status"
        ),
    )


class Alert(Record, Base):
    __tablename__ = "alerts"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"))
    alert_type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, default="warning")
    title: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str] = mapped_column(Text, default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    pushed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class ProviderUsage(Base):
    __tablename__ = "provider_usage"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    calls: Mapped[int] = mapped_column(Integer, default=0)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeat"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(UTCDateTime)
