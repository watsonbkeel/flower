from dataclasses import dataclass, replace
from datetime import datetime, timezone
import math


@dataclass(frozen=True)
class AirReading:
    status: str
    temperature_c: float | None = None
    humidity_pct: float | None = None
    observed_at: datetime | None = None
    provider: str = "unknown"
    source_type: str = "real"


class AirProviderSelector:
    def __init__(self, primary, wired=None, stale_seconds=300):
        self.primary, self.wired, self.stale_seconds = primary, wired, stale_seconds

    def read(self, now):
        latest = AirReading(status="STALE")
        for provider in (self.primary, self.wired):
            if provider is None:
                continue
            try:
                value = provider.read()
                latest = value
                if value.status == "READY" and value.observed_at:
                    age = (now - value.observed_at).total_seconds()
                    if (
                        0 <= age <= self.stale_seconds
                        and value.temperature_c is not None
                        and value.humidity_pct is not None
                    ):
                        if (
                            math.isfinite(value.temperature_c)
                            and -40 <= value.temperature_c <= 85
                            and 0 <= value.humidity_pct <= 100
                        ):
                            return value
                    latest = replace(value, status="STALE", temperature_c=None, humidity_pct=None)
            except Exception:
                latest = AirReading(status="STALE")
        return latest


class MockAir:
    def read(self):
        return AirReading("READY", 23, 50, datetime.now(timezone.utc), "mock", "mock")


class SHT30:
    def __init__(self):
        import board
        import adafruit_sht31d

        self.sensor = adafruit_sht31d.SHT31D(board.I2C())

    def read(self):
        return AirReading(
            "READY",
            self.sensor.temperature,
            self.sensor.relative_humidity,
            datetime.now(timezone.utc),
            "sht30",
        )


class XiaomiBLE:
    """Passive ATC1441 support; encrypted MiBeacon is explicitly unavailable."""

    def __init__(self, mac, bindkey=""):
        self.mac = mac.lower()
        self.bindkey_configured = bool(bindkey)
        self.latest = AirReading(status="NO_ADVERTISEMENT", provider="xiaomi_ble")

    def advertisement(self, device, advertisement):
        if device.address.lower() != self.mac:
            return
        for uuid, data in advertisement.service_data.items():
            if uuid.startswith("0000181a") and len(data) == 13:
                temperature = int.from_bytes(data[6:8], "big", signed=True) / 10
                self.latest = AirReading(
                    "READY", temperature, data[8], datetime.now(timezone.utc), "xiaomi_atc1441"
                )
                return
            if uuid.startswith("0000fe95") and len(data) >= 5:
                encrypted = bool(int.from_bytes(data[:2], "little") & 0x08)
                self.latest = AirReading(
                    "BINDKEY_REQUIRED"
                    if encrypted and not self.bindkey_configured
                    else "UNSUPPORTED_MODEL",
                    provider="xiaomi_ble",
                )
                return
        self.latest = AirReading("UNSUPPORTED_MODEL", provider="xiaomi_ble")

    async def scan(self, stop):
        import asyncio
        from bleak import BleakScanner

        async with BleakScanner(detection_callback=self.advertisement):
            while not stop.is_set():
                await asyncio.sleep(1)

    def read(self):
        return self.latest
