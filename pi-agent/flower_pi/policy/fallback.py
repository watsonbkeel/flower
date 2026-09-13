from datetime import datetime
import hashlib
import json
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    policy_version: int = Field(ge=1)
    profile_version: int = Field(ge=1)
    generated_at: datetime
    valid_until: datetime
    trigger_soil_below_pct: float = Field(ge=0, le=100)
    min_interval_hours: float = Field(ge=12)
    pulse_ml: float = Field(gt=0, le=15)
    max_pulses: int = Field(ge=1, le=1)
    max_session_ml: float = Field(gt=0, le=15)
    max_24h_ml: float = Field(gt=0, le=60)
    timezone: str
    allowed_windows_local: list[tuple[str, str]]
    profile_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_policy(self):
        from datetime import time
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError) as exc:
            raise ValueError("invalid policy timezone") from exc
        if self.generated_at.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("policy timestamps must be aware")
        duration = (self.valid_until - self.generated_at).total_seconds()
        if not 0 < duration <= 7 * 86400:
            raise ValueError("policy duration exceeds seven days")
        if not self.allowed_windows_local:
            raise ValueError("missing policy windows")
        for start, end in self.allowed_windows_local:
            if len(start) != 5 or len(end) != 5 or not time.fromisoformat(start) < time.fromisoformat(end):
                raise ValueError("windows must be HH:MM without midnight crossing")
        if self.pulse_ml != self.max_session_ml or self.pulse_ml > self.max_24h_ml:
            raise ValueError("invalid fallback dose limits")
        return self

    def verify(self, digest, minimum_version):
        if digest != policy_digest(self) or self.policy_version < minimum_version:
            raise ValueError("policy digest mismatch or rollback")

    def permits(self, now, *, soil_pct, last_watered, used_ml):
        import math
        if now.tzinfo is None or not self.generated_at <= now < self.valid_until:
            return False
        if not math.isfinite(soil_pct) or soil_pct >= self.trigger_soil_below_pct:
            return False
        if last_watered and (now - last_watered).total_seconds() < self.min_interval_hours * 3600:
            return False
        if used_ml + self.pulse_ml > self.max_24h_ml:
            return False
        local = now.astimezone(ZoneInfo(self.timezone)).strftime("%H:%M")
        return any(start <= local < end for start, end in self.allowed_windows_local)


def policy_digest(policy):
    content = policy.model_dump(mode="json") if isinstance(policy, Policy) else policy
    return "sha256:" + hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
