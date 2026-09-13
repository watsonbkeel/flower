import asyncio
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import signal
import threading
import time
from uuid import uuid4

from flower_pi.calibration import Calibration
from flower_pi.clock import TrustedClock
from flower_pi.cloud.client import CloudClient
from flower_pi.commands.executor import DispenseCommand, Executor
from flower_pi.config import PiSettings
from flower_pi.policy.fallback import Policy
from flower_pi.sensors.air import AirProviderSelector, MockAir, SHT30, XiaomiBLE
from flower_pi.sensors.soil import ADS1115, SoilFilter
from flower_pi.sensors.water_level import P451, WaterLevel
from flower_pi.state import DeviceState, ModeTracker
from flower_pi.storage.ledger import Ledger


def air_telemetry(air, source_type):
    age = (
        (datetime.now(timezone.utc) - air.observed_at).total_seconds()
        if air and air.observed_at
        else None
    )
    valid = bool(
        air
        and air.status == "READY"
        and air.source_type == source_type
        and age is not None
        and 0 <= age <= 300
    )
    return {
        "temperature_c": air.temperature_c if valid else None,
        "air_humidity": air.humidity_pct if valid else None,
        "sensor_health": {
            "air_source_type": air.source_type if air else None,
            "air_provider": air.provider if air else None,
            "air_age_sec": age,
        },
    }


class SensorLoop:
    def __init__(self, settings, calibration, pump, clock):
        self.settings, self.calibration, self.pump, self.clock = settings, calibration, pump, clock
        self.state = DeviceState()
        self.stop = threading.Event()
        self.water = False
        self.soil = None
        self.raw = None
        self.soil_at = 0
        self.water_at = 0
        self.air = None
        self.threads = []
        self.execution_activity = lambda: "IDLE"
        self.policy_live = lambda: False

    def spawn(self, target):
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        self.threads.append(thread)

    def start(self):
        def water_loop():
            sensor = P451() if self.settings.hardware_mode == "real" else None
            debounce = WaterLevel()
            while not self.stop.is_set():
                try:
                    raw_ok = sensor.read() if sensor else True
                    self.water = debounce.update(raw_ok, time.monotonic())
                    self.water_at = time.monotonic()
                    if not raw_ok:
                        self.pump.off()
                except Exception:
                    self.water = False
                    self.pump.off()
                self.stop.wait(0.05)

        def soil_loop():
            sensor = ADS1115() if self.settings.hardware_mode == "real" else None
            filtered = (
                SoilFilter(self.calibration.adc_dry, self.calibration.adc_wet)
                if self.calibration
                else None
            )
            while not self.stop.is_set():
                try:
                    self.raw = sensor.read() if sensor else 18000
                    self.soil = filtered.update(self.raw) if filtered else None
                    self.soil_at = time.monotonic()
                except Exception:
                    self.soil = None
                self.stop.wait(10)

        def air_loop():
            try:
                if self.settings.temp_humidity_provider == "mock":
                    selector = AirProviderSelector(MockAir())
                elif self.settings.temp_humidity_provider == "sht30":
                    selector = AirProviderSelector(SHT30())
                else:
                    ble = XiaomiBLE(self.settings.xiaomi_device_mac, self.settings.xiaomi_bindkey)
                    self.spawn(lambda: asyncio.run(ble.scan(self.stop)))
                    try:
                        fallback = SHT30()
                    except Exception:
                        fallback = None
                    selector = AirProviderSelector(ble, fallback)
                while not self.stop.is_set():
                    self.air = selector.read(datetime.now(timezone.utc))
                    self.stop.wait(5)
            except Exception:
                self.air = None

        for loop in (water_loop, soil_loop, air_loop):
            self.spawn(loop)

    def snapshot(self):
        now = time.monotonic()
        return replace(
            self.state,
            activity=self.execution_activity()
            if self.execution_activity() != "IDLE"
            else self.state.activity,
            profile_valid=self.policy_live(),
            water_level_ok=self.water and now - self.water_at < 2,
            soil_pct=self.soil if now - self.soil_at < 30 else None,
            time_trusted=self.clock.trusted(),
            calibration_valid=self.calibration is not None,
        )


def decode_command(data):
    parameters = dict(data["parameters"])
    parameters.pop("wait_after_pulse_sec", None)
    return DispenseCommand(
        **parameters,
        **{
            key: data[key]
            for key in (
                "id",
                "device_id",
                "source",
                "run_mode",
                "claim_deadline_at",
                "claimed_at",
                "start_grace_sec",
                "session_max_duration_sec",
            )
        },
    )


def refresh_policy(client, ledger):
    import httpx

    try:
        received = client.request("GET", "/fallback-policy")
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            ledger.set_value("fallback", {})
            return None
        raise
    candidate = Policy.model_validate(received["policy"])
    candidate.verify(received["policy_hash"], ledger.value("policy_version", 0))
    ledger.set_value("fallback", received)
    ledger.set_value("policy_version", candidate.policy_version)
    return candidate


def main():
    # LOW precedes config validation, disk, clocks, sensors and networking.
    from flower_pi.actuators.pump import GPIOPump, MockPump

    pump = GPIOPump() if os.environ.get("HARDWARE_MODE", "mock") == "real" else MockPump()
    pump.off()
    settings = PiSettings()
    clock = TrustedClock()
    ledger = Ledger(settings.local_db_path)
    ledger.recover(clock.utcnow() if clock.trusted() else None)
    try:
        calibration = Calibration.model_validate_json(settings.calibration_path.read_text())
    except (OSError, ValueError):
        calibration = None
    sensors = SensorLoop(settings, calibration, pump, clock)
    sensors.start()
    client = CloudClient(settings)
    tracker = ModeTracker()
    boot_path = Path("/proc/sys/kernel/random/boot_id")
    boot_id = boot_path.read_text().strip() if boot_path.exists() else str(uuid4())
    executor = Executor(
        "unknown",
        pump,
        ledger,
        sensors.snapshot,
        calibration,
        clock,
        limit_ml=settings.pump_max_24h_ml,
        interval_hours=settings.pump_min_interval_hours,
        boot_id=boot_id,
    )
    sensors.execution_activity = lambda: executor.activity

    def stop(*_):
        executor.stop()
        sensors.stop.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    last_cloud = float("-inf")
    prior_cloud = ledger.value("last_cloud_utc")
    if prior_cloud and clock.trusted():
        last_cloud = clock.monotonic() - max(0, clock.utcnow().timestamp() - prior_cloud)
    next_policy = 0
    policy = None
    cached = ledger.value("fallback")
    if cached:
        try:
            policy = Policy.model_validate(cached["policy"])
            policy.verify(cached["policy_hash"], ledger.value("policy_version", 0))
        except ValueError:
            policy = None

    def policy_live():
        return bool(
            policy
            and clock.trusted()
            and policy.generated_at <= clock.utcnow() < policy.valid_until
        )

    sensors.policy_live = policy_live

    def connected():
        nonlocal last_cloud
        last_cloud = clock.monotonic()

    def telemetry_sample():
        current = sensors.snapshot()
        mode = tracker.update(
            current,
            now_mono=clock.monotonic(),
            cloud_age=clock.monotonic() - last_cloud,
            policy_valid=policy_live(),
        )
        sensors.state = replace(sensors.state, operating_mode=mode)
        return {
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "soil_moisture": current.soil_pct,
            "soil_raw": sensors.raw,
            **air_telemetry(sensors.air, "real" if settings.hardware_mode == "real" else "mock"),
            "water_level_ok": current.water_level_ok,
            "operating_mode": mode,
            "activity": current.activity,
            "fault_codes": list(current.fault_codes),
            "time_trusted": current.time_trusted,
            "pump_commanded_on": pump.commanded_on,
            "source_type": "real" if settings.hardware_mode == "real" else "mock",
            "firmware_version": "2.2.2",
            "spec_version": "2.2.2",
        }

    from flower_pi.telemetry import TelemetryReporter

    reporter = TelemetryReporter(settings, sensors.stop, telemetry_sample, connected)
    reporter.start()
    try:
        while not sensors.stop.is_set():
            now_mono = clock.monotonic()
            trusted = clock.trusted()
            now = clock.utcnow() if trusted else datetime.now(timezone.utc)
            policy_valid = bool(
                policy and trusted and policy.generated_at <= now < policy.valid_until
            )
            sensors.state = replace(sensors.state, profile_valid=policy_valid, fault_codes=())
            current = sensors.snapshot()
            mode = tracker.update(
                current,
                now_mono=now_mono,
                cloud_age=now_mono - last_cloud,
                policy_valid=policy_valid,
            )
            faults = []
            if not current.water_level_ok:
                faults.append("LOW_WATER")
            if current.soil_pct is None:
                faults.append("SOIL_SENSOR_FAULT")
            if not trusted:
                faults.append("TIME_UNTRUSTED")
            if not calibration:
                faults.append("CALIBRATION_MISSING")
            if not policy_valid:
                faults.append("PROFILE_MISSING")
            if not sensors.air or sensors.air.status != "READY":
                faults.append("BLE_STALE")
            sensors.state = replace(sensors.state, operating_mode=mode, fault_codes=tuple(faults))
            if trusted:
                ledger.recover(now)
            try:
                for pending in ledger.pending():
                    client.request("POST", pending["route"], json=json.loads(pending["payload"]))
                    ledger.acknowledge(pending["id"])
                if now_mono >= next_policy:
                    try:
                        policy = refresh_policy(client, ledger)
                    except Exception:
                        pass
                    if calibration:
                        client.request(
                            "POST", "/calibration", json=calibration.model_dump(mode="json")
                        )
                    if trusted:
                        quota = client.request(
                            "POST",
                            "/quota/reconcile",
                            json={"used_24h_ml": ledger.used(now), "receipts": ledger.receipts()},
                        )
                        for receipt in quota.get("verified_receipts", []):
                            ledger.reconcile_receipt(receipt, now)
                        ledger.reconcile_used(quota["verified_cloud_used"], now)
                    next_policy = now_mono + 60
                claimed = client.request("POST", "/commands/claim")["command"]
                last_cloud = clock.monotonic()
                if clock.trusted():
                    ledger.set_value("last_cloud_utc", clock.utcnow().timestamp())
                executor.device_id = client.device_id
                if claimed:
                    cid = claimed["id"]
                    if claimed["action"] == "capture":
                        from flower_pi.camera.usb_camera import USBCamera

                        client.request("POST", f"/commands/{cid}/started")
                        sensors.state = replace(sensors.state, activity="CAPTURING")
                        try:
                            for shot in claimed["parameters"]["shots"]:
                                image = USBCamera(settings.camera_path).capture()
                                client.request(
                                    "POST",
                                    "/images",
                                    data={"plant_id": claimed["plant_id"], "image_type": shot},
                                    files={"file": ("capture.jpg", image, "image/jpeg")},
                                )
                            result = {"status": "succeeded", "actual_ml": 0, "pulses": []}
                        except Exception:
                            result = {"status": "failed", "reason": "CAMERA_UNAVAILABLE"}
                        finally:
                            sensors.state = replace(sensors.state, activity="IDLE")
                    else:
                        cmd = decode_command(claimed)
                        result = executor.execute(
                            cmd,
                            on_started=lambda: client.request("POST", f"/commands/{cid}/started"),
                            on_progress=lambda pulses: client.request(
                                "POST", f"/commands/{cid}/progress", json={"pulses": pulses}
                            ),
                        )
                    ledger.enqueue(
                        f"result:{cid}",
                        f"/commands/{cid}/result",
                        result,
                        datetime.now(timezone.utc),
                    )
            except Exception:
                if (
                    mode == "LOCAL_CONSERVATIVE"
                    and policy_valid
                    and calibration
                    and trusted
                    and ledger.value("fallback", {}).get("auto_mode") is True
                ):
                    command = DispenseCommand(
                        id=str(uuid4()),
                        device_id=executor.device_id,
                        source="local_fallback",
                        run_mode="real",
                        target_ml=policy.pulse_ml,
                        pulse_ml=policy.pulse_ml,
                        max_pulses=1,
                        max_continuous_sec=10,
                        afterdrip_settle_sec=30,
                        absorb_wait_sec=300,
                        session_max_duration_sec=460,
                        claim_deadline_at=now + timedelta(seconds=60),
                        stop_soil_pct=policy.trigger_soil_below_pct,
                    )
                    result = executor.execute(command, policy=policy)
                    ledger.enqueue(
                        f"fallback:{command.id}",
                        "/events/batch",
                        {
                            "events": [
                                {
                                    "event_id": command.id,
                                    "event_type": "local_fallback",
                                    "event_data": {
                                        "result": result,
                                        "reserved_ml": command.target_ml,
                                        "policy_version": policy.policy_version,
                                    },
                                    "human_readable": "离线保守补水 " + result["status"],
                                    "source_type": "real"
                                    if settings.hardware_mode == "real"
                                    else "mock",
                                    "occurred_at": now.isoformat(),
                                }
                            ]
                        },
                        now,
                    )
            sensors.stop.wait(settings.command_poll_interval_sec)
    finally:
        pump.off()
        sensors.stop.set()
        reporter.join(timeout=20)
        client.close()
        ledger.close()


if __name__ == "__main__":
    main()
