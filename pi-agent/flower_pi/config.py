from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PiSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)
    spec_version: Literal["2.2.2"] = "2.2.2"
    hardware_mode: Literal["mock", "real"] = "mock"
    app_env: Literal["development", "production"] = "development"
    server_base_url: str = "http://127.0.0.1:18082"
    device_code: str = "garden-001"
    device_secret: str = ""
    local_db_path: Path = Path(".runtime/pi-state.db")
    calibration_path: Path = Path(".runtime/calibration.json")
    camera_path: str = "/dev/v4l/by-id/UNCONFIGURED"
    pump_gpio: int = Field(default=17, ge=17, le=17)
    water_level_gpio: int = Field(default=27, ge=27, le=27)
    pump_max_24h_ml: float = Field(default=120, gt=0, le=120)
    pump_min_interval_hours: float = Field(default=6, ge=6)
    temp_humidity_provider: Literal["xiaomi_ble", "sht30", "mock"] = "mock"
    xiaomi_device_mac: str = ""
    xiaomi_bindkey: str = ""
    telemetry_interval_sec: float = Field(default=30, ge=1)
    command_poll_interval_sec: float = Field(default=5, ge=1)

    @model_validator(mode="after")
    def connection_security(self):
        url = urlsplit(self.server_base_url)
        if not url.hostname or url.username or url.password:
            raise ValueError("invalid SERVER_BASE_URL")
        if self.app_env == "production":
            if url.scheme != "https" or len(self.device_secret) < 32:
                raise ValueError("production requires HTTPS and independent device secret")
            if self.hardware_mode != "real" or self.temp_humidity_provider == "mock":
                raise ValueError("production cannot label mock hardware as real")
        elif url.scheme != "https" and url.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("development HTTP must use a loopback tunnel")
        return self
