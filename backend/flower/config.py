from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", hide_input_in_errors=True)
    app_env: Literal["development", "test", "production"] = "development"
    spec_version: Literal["2.2.2"] = "2.2.2"
    software_version: str = "development"
    app_base_url: str = "http://127.0.0.1:18082"
    dev_mode: bool = False
    dev_auth_bypass: bool = False
    secret_key: str = ""
    database_url: str = "sqlite:///.runtime/flower-dev.db"
    upload_dir: Path = Path(".runtime/uploads")
    max_upload_mb: int = Field(default=10, ge=1, le=10)
    min_upload_free_bytes: int = Field(default=1073741824, ge=0)
    image_retention_days: int = 90
    telemetry_raw_retention_days: int = 30
    telemetry_hourly_retention_days: int = 365
    command_claim_ttl_sec: int = Field(default=60, ge=1, le=60)
    command_start_grace_sec: int = Field(default=30, ge=1, le=30)
    session_max_duration_hard_sec: int = Field(default=1800, ge=1, le=1800)
    session_safety_margin_sec: int = 120
    device_offline_sec: int = 90
    run_mode: Literal["real", "demo", "offline_demo"] = "real"
    soil_absorb_wait_sec: int = Field(default=300, ge=300)
    demo_absorb_wait_sec: int = Field(default=45, ge=45)
    pump_afterdrip_settle_sec: int = Field(default=30, ge=30)
    pump_max_continuous_sec: float = Field(default=10, gt=0, le=10)
    max_pulses_limit: int = Field(default=3, ge=1, le=3)
    max_single_session_ml: float = Field(default=60, gt=0, le=60)
    pump_max_24h_ml: float = Field(default=120, gt=0, le=120)
    pump_min_interval_hours: float = Field(default=6, ge=6)
    urgent_override_gap_pct: float = Field(default=15, ge=15)
    job_max_concurrency: int = Field(default=1, ge=1, le=1)
    job_recovery_scan_sec: int = 60
    alert_dedup_hours: int = 6
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    provider_mode: Literal["mock", "http"] = "mock"
    provider_base_url: str = ""
    provider_api_key: str = ""
    provider_timeout_sec: float = Field(default=15, gt=0, le=30)
    provider_daily_limit: int = 100

    @model_validator(mode="after")
    def fail_closed(self):
        url = urlsplit(self.app_base_url)
        if not url.hostname or url.username or url.password:
            raise ValueError("APP_BASE_URL must have a host and no credentials")
        if self.app_env == "production":
            if self.dev_mode or self.dev_auth_bypass:
                raise ValueError("development flags forbidden in production")
            if url.scheme != "https":
                raise ValueError("HTTPS required in production")
            if len(self.secret_key) < 32 or self.secret_key.lower().startswith("change"):
                raise ValueError("independent SECRET_KEY required")
            db = urlsplit(self.database_url)
            if db.scheme != "postgresql+psycopg" or not db.password or not db.hostname:
                raise ValueError("independent PostgreSQL credentials required")
        elif url.scheme != "https" and url.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("development HTTP is loopback only")
        return self
