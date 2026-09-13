from datetime import datetime, timedelta, time
import hashlib
import json
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, HttpUrl, TypeAdapter, model_validator

from flower.schemas import StrictModel, SourceType


class TemperatureRange(StrictModel):
    min: float = Field(ge=-20, le=50)
    max: float = Field(ge=-20, le=50)

    @model_validator(mode="after")
    def ordered(self):
        if self.min >= self.max:
            raise ValueError("temperature range invalid")
        return self


class Knowledge(StrictModel):
    preferred_temperature_c: TemperatureRange = Field(
        default_factory=lambda: TemperatureRange(min=18, max=30)
    )
    soil_preference: str = "slightly_dry_between_watering"
    soil_target_min_pct: float = Field(default=40, ge=10, le=70)
    soil_target_max_pct: float = Field(default=65, ge=20, le=90)
    watering_windows: list[Literal["early_morning", "early_evening"]] = Field(
        default_factory=lambda: ["early_morning", "early_evening"]
    )
    rain_sensitive: bool = True
    drought_tolerance: Literal["low", "medium", "high"] = "low"
    waterlogging_tolerance: Literal["low", "medium", "high"] = "low"
    notes: list[str] = Field(default_factory=list, max_length=20)
    source_ids: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(default=0, ge=0, le=1)
    needs_review: bool = True

    @model_validator(mode="after")
    def ordered(self):
        if self.soil_target_min_pct >= self.soil_target_max_pct or not self.watering_windows:
            raise ValueError("invalid care range or windows")
        return self


class CareSource(StrictModel):
    id: str
    url: HttpUrl
    title: str
    summary: str = Field(max_length=10000)
    category: Literal["botanical", "extension", "horticultural", "other"]
    retrieved_at: AwareDatetime
    confidence: float = Field(ge=0, le=1)
    source_type: SourceType
    conflict: bool = False


class Weather(StrictModel):
    temperature_c: float | None = Field(default=None, ge=-40, le=60)
    rain_next_12h_mm: float = Field(default=0, ge=0, le=1000)
    observed_at: AwareDatetime
    valid_until: AwareDatetime
    provider: str
    source_type: SourceType


class MemoryRule(StrictModel):
    preferred_windows: list[tuple[str, str]] = Field(default_factory=list)
    watering_style: Literal["small_portions", "normal", "thorough"] = "normal"
    soil_preference: Literal["let_surface_dry", "normal"] = "normal"
    threshold_shift_pct: float = Field(default=0, ge=-5, le=5)
    requires_confirmation: Literal[True] = True
    source_type: Literal["family_memory"] = "family_memory"

    @model_validator(mode="after")
    def windows_valid(self):
        validate_windows(self.preferred_windows)
        return self


def validate_windows(windows):
    for start, end in windows:
        if len(start) != 5 or len(end) != 5 or time.fromisoformat(start) >= time.fromisoformat(end):
            raise ValueError("windows must use HH:MM without midnight crossing")


def digest(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
    )


def compile_policy(
    *, profile, profile_version, policy_version, now, timezone_name, windows, pulse_ml, max_24h_ml
):
    ZoneInfo(timezone_name)
    validate_windows(windows)
    if not windows or now.tzinfo is None:
        raise ValueError("policy timezone and windows required")
    pulse = float(min(pulse_ml, 10))
    policy = {
        "policy_version": policy_version,
        "profile_version": profile_version,
        "generated_at": TypeAdapter(datetime).dump_python(now, mode="json"),
        "valid_until": TypeAdapter(datetime).dump_python(now + timedelta(days=7), mode="json"),
        "trigger_soil_below_pct": float(max(0, profile["soil_target_min_pct"] - 12)),
        "min_interval_hours": 12.0,
        "pulse_ml": pulse,
        "max_pulses": 1,
        "max_session_ml": pulse,
        "max_24h_ml": float(min(max_24h_ml / 2, 60)),
        "timezone": timezone_name,
        "allowed_windows_local": [list(w) for w in windows],
        "profile_hash": digest(profile),
    }
    return {"policy": policy, "policy_hash": digest(policy)}
