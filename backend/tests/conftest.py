from datetime import datetime, timezone
import os

from alembic import command
from fastapi.testclient import TestClient
import pytest

from flower.config import Settings
from flower.db import migration_config
from flower.main import create_app
from flower.models import Base, User, Device, Plant, CareProfile, DeviceStatus
from flower.auth import hash_secret, issue_token


@pytest.fixture
def system(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    settings = Settings(
        app_env="test",
        database_url=url,
        secret_key="test-signing-" + "x" * 40,
        upload_dir=tmp_path / "uploads",
    )
    app = create_app(settings)
    config = migration_config()
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    with app.state.engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name != "schema_info":
                conn.execute(table.delete())
    now = datetime.now(timezone.utc)
    with app.state.sessions.begin() as db:
        user = User(openid="mock-owner")
        db.add(user)
        db.flush()
        device = Device(
            owner_user_id=user.id,
            device_code="test-device",
            secret_hash=hash_secret("test-device-secret-" + "s" * 32),
            operating_mode="FULL",
            activity="IDLE",
            fault_codes=[],
            time_trusted=True,
            last_seen_at=now,
            firmware_version="test",
            source_type="mock",
            calibration={
                "flow_ml_sec": 3,
                "afterdrip_mean_ml": 1,
                "afterdrip_max_ml": 1,
                "min_run_sec": 1,
                "adc_dry": 20000,
                "adc_wet": 10000,
                "insert_depth_mark": "4cm",
                "calibrated_at": now.isoformat(),
            },
        )
        db.add(device)
        db.flush()
        plant = Plant(
            user_id=user.id,
            device_id=device.id,
            name="Jasmine",
            common_name="Jasmine",
            scientific_name="Jasminum sambac",
            recognition_confirmed=True,
            auto_mode=True,
            city="Shanghai",
            timezone="Asia/Shanghai",
            pot_size="small",
            pot_material="plastic",
            has_drainage=True,
            placement_type="indoor",
        )
        db.add(plant)
        db.flush()
        from datetime import timedelta

        profile = CareProfile(
            plant_id=plant.id,
            version=1,
            confirmed=True,
            valid_until=now + timedelta(days=30),
            profile={
                "soil_target_min_pct": 40,
                "soil_target_max_pct": 65,
                "watering_windows": ["early_morning", "early_evening"],
            },
        )
        db.add(profile)
        db.add(
            DeviceStatus(
                device_id=device.id,
                soil_moisture=20,
                soil_raw=18000,
                operating_mode="FULL",
                activity="IDLE",
                fault_codes=[],
                water_level_ok=True,
                pump_commanded_on=False,
                used_24h_ml=0,
                reported_at=now,
                source_type="mock",
            )
        )
        db.flush()
        user_id, device_id, plant_id = user.id, device.id, plant.id
    with TestClient(app) as client:
        yield dict(
            app=app,
            client=client,
            settings=settings,
            user_id=user_id,
            device_id=device_id,
            plant_id=plant_id,
            user_headers={"Authorization": "Bearer " + issue_token(settings, user_id, "user")},
            device_headers={
                "Authorization": "Bearer " + issue_token(settings, device_id, "device")
            },
        )
    app.state.engine.dispose()
