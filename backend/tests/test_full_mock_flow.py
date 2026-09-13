from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from flower.models import CareProfile, WateringSession
from flower.worker import Worker
from flower_pi.actuators.pump import MockPump
from flower_pi.calibration import Calibration
from flower_pi.commands.executor import Executor
from flower_pi.main import decode_command
from flower_pi.state import DeviceState
from flower_pi.storage.ledger import Ledger


def test_full_offline_demo_uses_both_gates_and_persists_actual_mock_result(system, tmp_path):
    client, headers, device_headers = (
        system["client"],
        system["user_headers"],
        system["device_headers"],
    )
    pid = system["plant_id"]
    system["settings"].run_mode = "offline_demo"
    worker = Worker(system["app"].state.sessions, system["settings"])
    uploaded = client.post(
        "/api/v1/device/images",
        headers=device_headers,
        data={"plant_id": pid, "image_type": "whole"},
        files={"file": ("sample.jpg", Path("miniapp/assets/plant.jpg").read_bytes(), "image/jpeg")},
    )
    assert uploaded.status_code == 202
    assert worker.run_once()
    recognition = client.get(f"/api/v1/plants/{pid}/recognition", headers=headers).json()
    candidate = recognition["result"]["candidates"][0]
    assert recognition["result"]["source_type"] == "mock"
    assert (
        client.post(
            f"/api/v1/plants/{pid}/confirm-species",
            headers=headers,
            json={
                "common_name": candidate["common_name"],
                "scientific_name": candidate["scientific_name"],
                "input_method": "recognition",
                "confidence": candidate["confidence"],
            },
        ).status_code
        == 200
    )
    assert (
        client.post(f"/api/v1/plants/{pid}/care-profile/generate", headers=headers).status_code
        == 202
    )
    assert worker.run_once()
    with system["app"].state.sessions() as db:
        profile = db.scalar(
            select(CareProfile)
            .where(CareProfile.plant_id == pid)
            .order_by(CareProfile.version.desc())
        )
        profile_id = profile.id
    assert (
        client.post(
            f"/api/v1/plants/{pid}/care-profile/confirm",
            headers=headers,
            json={"profile_id": profile_id},
        ).status_code
        == 200
    )
    response = client.post(
        f"/api/v1/plants/{pid}/water",
        headers=headers | {"Idempotency-Key": "offline-demo"},
        json={"quantity": 20, "unit": "ml"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    cmd = client.post("/api/v1/device/commands/claim", headers=device_headers).json()["command"]

    class Clock:
        value = 0

        def utcnow(self):
            return datetime.now(timezone.utc)

        def monotonic(self):
            return self.value

        def sleep(self, seconds):
            self.value += seconds

    calibration = Calibration(
        flow_ml_sec=3,
        afterdrip_mean_ml=1,
        afterdrip_max_ml=1,
        min_run_sec=1,
        adc_dry=20000,
        adc_wet=10000,
        insert_depth_mark="MOCK",
        calibrated_at=datetime.now(timezone.utc),
    )
    state = DeviceState(
        operating_mode="FULL",
        activity="IDLE",
        water_level_ok=True,
        soil_pct=20,
        time_trusted=True,
        calibration_valid=True,
        profile_valid=True,
    )
    pump, ledger, clock = MockPump(), Ledger(tmp_path / "pi.db"), Clock()
    executor = Executor(system["device_id"], pump, ledger, lambda: state, calibration, clock)

    def started():
        assert (
            client.post(
                f"/api/v1/device/commands/{cmd['id']}/started", headers=device_headers
            ).status_code
            == 200
        )

    def progress(pulses):
        assert (
            client.post(
                f"/api/v1/device/commands/{cmd['id']}/progress",
                headers=device_headers,
                json={"pulses": pulses},
            ).status_code
            == 200
        )

    result = executor.execute(decode_command(cmd), on_started=started, on_progress=progress)
    assert result["status"] == "succeeded"
    assert clock.value > 60
    assert pump.starts == 2
    assert not pump.commanded_on
    response = client.post(
        f"/api/v1/device/commands/{cmd['id']}/result", headers=device_headers, json=result
    )
    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    reconciliation = client.post(
        "/api/v1/device/quota/reconcile",
        headers=device_headers,
        json={"used_24h_ml": ledger.used(clock.utcnow()), "receipts": ledger.receipts()},
    )
    assert reconciliation.status_code == 200
    receipts = reconciliation.json()["verified_receipts"]
    assert len(receipts) == 1
    assert ledger.reconcile_receipt(receipts[0], clock.utcnow())
    with system["app"].state.sessions() as db:
        session = db.scalar(select(WateringSession).where(WateringSession.command_id == cmd["id"]))
        assert session.source_type == "mock"
        assert session.actual_ml == 20
    state = replace(state, operating_mode="SAFE_HOLD")
    rejected = executor.execute(decode_command(cmd).model_copy(update={"id": "forbidden"}))
    assert rejected["status"] == "failed"
    assert pump.starts == 2
    ledger.close()
