"""Loopback-only development stack with an explicitly simulated Flower device."""

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import threading
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "pi-agent")]


def seed(settings, device_secret):
    from sqlalchemy import select
    from flower.auth import hash_secret
    from flower.db import make_engine, sessions
    from flower.models import (
        User,
        Device,
        Plant,
        CareProfile,
        DeviceStatus,
        Telemetry,
        Memory,
        Event,
        utcnow,
    )
    from flower.services.care import research, issue_fallback
    from flower.services.providers import MockProviders

    engine = make_engine(settings.database_url)
    with sessions(engine).begin() as db:
        existing = db.scalar(select(Device).where(Device.device_code == "garden-mock"))
        if existing:
            return existing.id
        now = utcnow()
        user = User(openid="mock-demo", nickname="开发体验")
        db.add(user)
        db.flush()
        calibration = {
            "flow_ml_sec": 3,
            "afterdrip_mean_ml": 1,
            "afterdrip_max_ml": 1,
            "min_run_sec": 1,
            "adc_dry": 20000,
            "adc_wet": 10000,
            "insert_depth_mark": "MOCK",
            "calibrated_at": now.isoformat(),
        }
        device = Device(
            owner_user_id=user.id,
            device_code="garden-mock",
            name="窗边守护器",
            secret_hash=hash_secret(device_secret),
            source_type="mock",
            operating_mode="FULL",
            activity="IDLE",
            fault_codes=[],
            time_trusted=True,
            last_seen_at=now,
            calibration=calibration,
        )
        db.add(device)
        db.flush()
        plant = Plant(
            user_id=user.id,
            device_id=device.id,
            name="窗边的茉莉",
            common_name="茉莉",
            scientific_name="Jasminum sambac",
            recognition_confirmed=True,
            city="上海",
            timezone="Asia/Shanghai",
            pot_size="small",
            pot_material="terracotta",
            has_drainage=True,
            placement_type="indoor",
            auto_mode=False,
            created_at=now - timedelta(days=2),
        )
        db.add(plant)
        db.flush()
        profile = CareProfile(
            plant_id=plant.id,
            version=1,
            profile=research(MockProviders(), {}),
            confirmed=True,
            confirmed_at=now,
            valid_until=now + timedelta(days=30),
        )
        db.add(profile)
        db.flush()
        issue_fallback(db, settings, plant, profile)
        db.add(
            DeviceStatus(
                device_id=device.id,
                operating_mode="FULL",
                activity="IDLE",
                fault_codes=[],
                soil_moisture=31,
                soil_raw=16900,
                temperature_c=25,
                air_humidity=58,
                water_level_ok=True,
                pump_commanded_on=False,
                used_24h_ml=0,
                reported_at=now,
                source_type="mock",
            )
        )
        for i in range(97):
            occurred = now - timedelta(minutes=30 * (96 - i))
            db.add(
                Telemetry(
                    device_id=device.id,
                    plant_id=plant.id,
                    event_id=f"seed:{i}",
                    soil_moisture=round(44 - i * 0.13 + math.sin(i / 7), 1),
                    soil_raw=16900,
                    temperature_c=25,
                    air_humidity=58,
                    water_level_ok=True,
                    source_type="mock",
                    extra_data={"fixture": "explicit_generated_mock"},
                    occurred_at=occurred,
                )
            )
        db.add(
            Memory(
                user_id=user.id,
                plant_id=plant.id,
                title="外公的养花笔记",
                story="夏天傍晚，他总会去窗边看看花。",
                original_experience="茉莉土干了，傍晚少量浇。",
                structured_rule=MockProviders().structure_memory(""),
                rule_confirmed=False,
                rule_enabled=False,
            )
        )
        for i, message in enumerate(
            ["模拟设备已连接，等待养护判断", "模拟养护卡已确认", "已开始记录模拟土壤数据"]
        ):
            db.add(
                Event(
                    device_id=device.id,
                    plant_id=plant.id,
                    event_id=f"seed-event:{i}",
                    event_type="demo_setup",
                    human_readable=message,
                    source_type="mock",
                    occurred_at=now - timedelta(minutes=i * 20),
                )
            )
        return device.id


class AcceleratedClock:
    def __init__(self):
        self.elapsed = 0

    def utcnow(self):
        return datetime.now(timezone.utc)

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.elapsed += seconds
        time.sleep(0.00005)


def mock_device(settings, secret, stop):
    from flower_pi.actuators.pump import MockPump
    from flower_pi.calibration import Calibration
    from flower_pi.cloud.client import CloudClient
    from flower_pi.config import PiSettings
    from flower_pi.commands.executor import Executor
    from flower_pi.main import decode_command
    from flower_pi.state import DeviceState
    from flower_pi.storage.ledger import Ledger

    client = CloudClient(
        PiSettings(
            server_base_url=settings.app_base_url, device_code="garden-mock", device_secret=secret
        )
    )
    clock = AcceleratedClock()
    ledger = Ledger(ROOT / ".runtime/mock-ledger.db")
    ledger.recover(clock.utcnow())
    calibration = Calibration(
        flow_ml_sec=3,
        afterdrip_mean_ml=1,
        afterdrip_max_ml=1,
        min_run_sec=1,
        adc_dry=20000,
        adc_wet=10000,
        insert_depth_mark="MOCK",
        calibrated_at=clock.utcnow(),
    )
    state = DeviceState(
        operating_mode="FULL",
        activity="IDLE",
        soil_pct=31,
        water_level_ok=True,
        time_trusted=True,
        calibration_valid=True,
        profile_valid=True,
    )
    pump = MockPump()
    executor = None
    try:
        while not stop.is_set():
            try:
                now = clock.utcnow()
                client.request(
                    "POST",
                    "/telemetry",
                    json={
                        "event_id": str(uuid4()),
                        "occurred_at": now.isoformat(),
                        "soil_moisture": 31,
                        "soil_raw": 16900,
                        "temperature_c": 25,
                        "air_humidity": 58,
                        "water_level_ok": True,
                        "operating_mode": "FULL",
                        "activity": "IDLE",
                        "fault_codes": [],
                        "time_trusted": True,
                        "used_24h_ml": ledger.used(now),
                        "source_type": "mock",
                        "firmware_version": "simulator",
                        "spec_version": "2.2.2",
                        "sensor_health": {"air_age_sec": 0},
                    },
                )
                if executor is None:
                    executor = Executor(
                        client.device_id, pump, ledger, lambda: state, calibration, clock
                    )
                command = client.request("POST", "/commands/claim")["command"]
                if command:
                    cid = command["id"]
                    if command["action"] == "capture":
                        client.request("POST", f"/commands/{cid}/started")
                        client.request(
                            "POST",
                            "/images",
                            data={"plant_id": command["plant_id"], "image_type": "whole"},
                            files={
                                "file": (
                                    "mock.jpg",
                                    (ROOT / "miniapp/assets/plant.jpg").read_bytes(),
                                    "image/jpeg",
                                )
                            },
                        )
                        result = {"status": "succeeded", "actual_ml": 0, "pulses": []}
                    else:
                        result = executor.execute(
                            decode_command(command),
                            on_started=lambda: client.request("POST", f"/commands/{cid}/started"),
                            on_progress=lambda pulses: client.request(
                                "POST", f"/commands/{cid}/progress", json={"pulses": pulses}
                            ),
                        )
                    client.request("POST", f"/commands/{cid}/result", json=result)
            except Exception:
                pass
            stop.wait(3)
    finally:
        pump.off()
        client.close()
        ledger.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18082)
    args = parser.parse_args()
    os.chdir(ROOT)
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    config_path = runtime / "dev-config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
    else:
        config = {
            "secret_key": secrets.token_urlsafe(48),
            "device_secret": secrets.token_urlsafe(48),
        }
        config_path.write_text(json.dumps(config))
        config_path.chmod(0o600)
    from alembic import command
    from flower.config import Settings
    from flower.db import migration_config

    settings = Settings(
        app_env="development",
        secret_key=config["secret_key"],
        database_url=f"sqlite:///{runtime / 'flower-dev.db'}",
        app_base_url=f"http://127.0.0.1:{args.port}",
        upload_dir=runtime / "uploads",
        provider_mode="mock",
    )
    migration = migration_config()
    migration.attributes["database_url"] = settings.database_url
    command.upgrade(migration, "head")
    seed(settings, config["device_secret"])
    env = (
        os.environ
        | {key.upper(): str(value) for key, value in settings.model_dump().items()}
        | {"PYTHONPATH": str(ROOT / "backend")}
    )
    children = [
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "flower.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.port),
            ],
            env=env,
        ),
        subprocess.Popen([sys.executable, "-m", "flower.worker"], env=env),
    ]
    stop = threading.Event()
    thread = threading.Thread(
        target=mock_device, args=(settings, config["device_secret"], stop), daemon=True
    )
    thread.start()

    def shutdown(*_):
        stop.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    print(f"Development mock preview: {settings.app_base_url}/preview/", flush=True)
    try:
        while not stop.wait(1):
            if any(child.poll() is not None for child in children):
                raise RuntimeError("Development child process stopped")
    finally:
        stop.set()
        thread.join(timeout=15)
        for child in children:
            child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
