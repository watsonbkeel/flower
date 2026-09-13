from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

SourceType = Literal["real", "demo", "imported_test", "mock"]
OperatingMode = Literal["STARTING", "FULL", "LOCAL_CONSERVATIVE", "SAFE_HOLD"]
Activity = Literal["IDLE", "CAPTURING", "CALIBRATING", "WATERING"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class DeviceLogin(StrictModel):
    device_code: str = Field(min_length=1, max_length=100)
    device_secret: str = Field(min_length=1, max_length=256)


class WaterRequest(StrictModel):
    quantity: float = Field(gt=0, le=60)
    unit: Literal["ml", "portion"] = "ml"


class TelemetryInput(StrictModel):
    event_id: str = Field(min_length=1, max_length=100)
    occurred_at: AwareDatetime
    soil_moisture: float | None = Field(default=None, ge=0, le=100)
    soil_raw: float | None = Field(default=None, ge=0, le=32767)
    temperature_c: float | None = Field(default=None, ge=-40, le=85)
    air_humidity: float | None = Field(default=None, ge=0, le=100)
    water_level_ok: bool
    operating_mode: OperatingMode
    activity: Activity
    fault_codes: list[str] = Field(max_length=30)
    time_trusted: bool
    used_24h_ml: float = Field(ge=0, le=10000)
    pump_commanded_on: bool = False
    sensor_health: dict = Field(default_factory=dict)
    source_type: SourceType
    firmware_version: str = Field(max_length=100)
    spec_version: Literal["2.2.2"]


class Pulse(StrictModel):
    pulse: int = Field(ge=1, le=3)
    estimated_ml: float = Field(gt=0, le=40)
    finished_at: AwareDatetime


class ProgressInput(StrictModel):
    pulses: list[Pulse] = Field(default_factory=list, max_length=3)


class ResultInput(ProgressInput):
    status: Literal["succeeded", "failed", "timed_out", "cancelled"]
    actual_ml: float = Field(default=0, ge=0, le=60)
    provisional: bool = False
    reason: str | None = Field(default=None, max_length=100)


class CalibrationInput(StrictModel):
    flow_ml_sec: float = Field(gt=0, le=30)
    afterdrip_mean_ml: float = Field(ge=0, le=3)
    afterdrip_max_ml: float = Field(ge=0, le=3)
    min_run_sec: float = Field(gt=0, le=10)
    adc_dry: float = Field(ge=0, le=32767)
    adc_wet: float = Field(ge=0, le=32767)
    insert_depth_mark: str = Field(min_length=1, max_length=100)
    calibrated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_span(self):
        if (
            abs(self.adc_dry - self.adc_wet) < 1000
            or self.afterdrip_mean_ml > self.afterdrip_max_ml
        ):
            raise ValueError("invalid calibration span or afterdrip")
        return self


class EventInput(StrictModel):
    event_id: str = Field(min_length=1, max_length=100)
    event_type: str = Field(min_length=1, max_length=100)
    severity: Literal["info", "warning", "error"] = "info"
    event_data: dict = Field(default_factory=dict)
    human_readable: str = Field(max_length=2000)
    source_type: SourceType
    occurred_at: AwareDatetime


class EventBatch(StrictModel):
    events: list[EventInput] = Field(max_length=100)


class QuotaInput(StrictModel):
    used_24h_ml: float = Field(ge=0, le=10000)


def serialize(record):
    result = {column.name: getattr(record, column.name) for column in record.__table__.columns}
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in result.items()
        if key not in {"secret_hash", "openid", "request_hash"}
    }
