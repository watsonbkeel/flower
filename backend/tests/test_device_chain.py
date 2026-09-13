from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from flower.models import Command, Plant, Device, DeviceStatus
from flower.services.commands import create_command, claim_command, sweep_commands


def water(system, **payload):
    return system["client"].post(
        f"/api/v1/plants/{system['plant_id']}/water",
        headers=system["user_headers"] | {"Idempotency-Key": "water-test"},
        json={"quantity": 20, "unit": "ml"} | payload,
    )


def test_device_auth_and_token_scoping(system):
    client = system["client"]
    assert client.post("/api/v1/device/commands/claim").status_code == 401
    assert (
        client.post("/api/v1/device/commands/claim", headers=system["user_headers"]).status_code
        == 403
    )
    assert client.get("/api/v1/plants", headers=system["device_headers"]).status_code == 403
    response = client.post(
        "/api/v1/device/auth/token",
        json={"device_code": "test-device", "device_secret": "test-device-secret-" + "s" * 32},
    )
    assert response.status_code == 200
    assert response.json()["device_id"] == system["device_id"]
    assert "secret" not in response.text
    assert (
        client.post(
            "/api/v1/device/auth/token",
            json={"device_code": "test-device", "device_secret": "wrong"},
        ).status_code
        == 401
    )


def test_pending_is_not_success_and_retry_is_idempotent(system):
    first = water(system)
    assert first.status_code == 202
    assert first.json()["status"] == "pending"
    assert water(system).json()["id"] == first.json()["id"]
    assert water(system, quantity=30).status_code == 409


def test_atomic_hundred_claims_only_one_winner(system):
    assert water(system).status_code == 202

    def claim(_):
        with system["app"].state.sessions.begin() as db:
            return claim_command(db, system["device_id"], datetime.now(timezone.utc))

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(claim, range(100)))
    assert sum(result is not None for result in results) == 1


def test_claim_and_session_clocks_separate_progress_does_not_extend(system):
    response = water(system)
    command_id = response.json()["id"]
    client, headers = system["client"], system["device_headers"]
    claimed = client.post("/api/v1/device/commands/claim", headers=headers)
    assert claimed.json()["command"]["id"] == command_id
    started = client.post(f"/api/v1/device/commands/{command_id}/started", headers=headers)
    assert started.status_code == 200
    deadline = started.json()["session_deadline_at"]
    with system["app"].state.sessions.begin() as db:
        cmd = db.get(Command, command_id)
        cmd.claim_deadline_at = datetime.now(timezone.utc) - timedelta(seconds=70)
        sweep_commands(db, datetime.now(timezone.utc))
        assert cmd.status == "executing"
    progress = client.post(
        f"/api/v1/device/commands/{command_id}/progress",
        headers=headers,
        json={
            "pulses": [
                {
                    "pulse": 1,
                    "estimated_ml": 10,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        },
    )
    assert progress.status_code == 200
    assert progress.json()["session_deadline_at"] == deadline
    pulses = [
        {"pulse": i, "estimated_ml": 10, "finished_at": datetime.now(timezone.utc).isoformat()}
        for i in (1, 2)
    ]
    result = client.post(
        f"/api/v1/device/commands/{command_id}/result",
        headers=headers,
        json={"status": "succeeded", "actual_ml": 20, "pulses": pulses},
    )
    assert result.status_code == 200
    assert result.json()["status"] == "succeeded"
    assert (
        client.post(
            f"/api/v1/device/commands/{command_id}/result",
            headers=headers,
            json={"status": "succeeded", "actual_ml": 20, "pulses": pulses},
        ).status_code
        == 200
    )


def test_success_cannot_lower_quota_without_matching_pulse_receipts(system):
    cid = water(system).json()["id"]
    client, headers = system["client"], system["device_headers"]
    client.post("/api/v1/device/commands/claim", headers=headers)
    client.post(f"/api/v1/device/commands/{cid}/started", headers=headers)
    response = client.post(
        f"/api/v1/device/commands/{cid}/result",
        headers=headers,
        json={"status": "succeeded", "actual_ml": 10, "pulses": []},
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "initial, expected, field",
    [
        ("pending", "expired", "claim_deadline_at"),
        ("claimed", "failed", "claimed_at"),
        ("executing", "timed_out", "session_deadline_at"),
    ],
)
def test_timeout_sweeper(system, initial, expected, field):
    cid = water(system).json()["id"]
    now = datetime.now(timezone.utc)
    with system["app"].state.sessions.begin() as db:
        cmd = db.get(Command, cid)
        cmd.status = initial
        setattr(cmd, field, now - timedelta(seconds=100))
        db.flush()
        sweep_commands(db, now)
        db.refresh(cmd)
        assert cmd.status == expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("water_level_ok", False),
        ("soil_moisture", None),
        ("activity", "WATERING"),
        ("used_24h_ml", 115),
    ],
)
def test_cloud_safety_gate(system, field, value):
    with system["app"].state.sessions.begin() as db:
        setattr(db.get(DeviceStatus, system["device_id"]), field, value)
    assert water(system).status_code == 409


def test_untrusted_time_and_stale_telemetry_reject(system):
    with system["app"].state.sessions.begin() as db:
        db.get(Device, system["device_id"]).time_trusted = False
    assert water(system).status_code == 409


def test_database_partial_unique_indexes(system):
    with pytest.raises(IntegrityError):
        with system["app"].state.sessions.begin() as db:
            db.add(Plant(user_id=system["user_id"], device_id=system["device_id"], name="Second"))
    cid = water(system).json()["id"]
    with pytest.raises(IntegrityError):
        with system["app"].state.sessions.begin() as db:
            original = db.get(Command, cid)
            values = {
                c.name: getattr(original, c.name)
                for c in Command.__table__.columns
                if c.name not in {"id", "idempotency_key"}
            }
            db.add(Command(**values, idempotency_key="other"))


def test_remote_maintenance_cannot_be_created(system):
    with pytest.raises(ValueError):
        with system["app"].state.sessions.begin() as db:
            create_command(
                db,
                system["settings"],
                device_id=system["device_id"],
                plant_id=system["plant_id"],
                user_id=system["user_id"],
                capability="dispenser",
                action="dispense",
                parameters={"quantity": 20, "unit": "ml"},
                source="maintenance_test",
                run_mode="real",
                idempotency_key="maintenance",
            )


def test_telemetry_authenticity_and_out_of_order_status(system):
    now = datetime.now(timezone.utc)
    payload = dict(
        event_id="telemetry-1",
        occurred_at=now.isoformat(),
        soil_moisture=25,
        soil_raw=17000,
        water_level_ok=True,
        operating_mode="FULL",
        activity="IDLE",
        fault_codes=[],
        time_trusted=True,
        used_24h_ml=0,
        source_type="mock",
        firmware_version="test",
        spec_version="2.2.2",
    )
    client, headers = system["client"], system["device_headers"]
    assert client.post("/api/v1/device/telemetry", headers=headers, json=payload).status_code == 200
    assert client.post("/api/v1/device/telemetry", headers=headers, json=payload).status_code == 200
    older = payload | {
        "event_id": "telemetry-old",
        "occurred_at": (now - timedelta(hours=1)).isoformat(),
        "soil_moisture": 5,
    }
    assert client.post("/api/v1/device/telemetry", headers=headers, json=older).status_code == 200
    with system["app"].state.sessions() as db:
        assert db.get(DeviceStatus, system["device_id"]).soil_moisture == 25
    assert (
        client.post(
            "/api/v1/device/telemetry",
            headers=headers,
            json=payload | {"source_type": "real", "event_id": "lie"},
        ).status_code
        == 409
    )
