from datetime import timedelta
from sqlalchemy import select

from flower.models import Command, WateringSession, utcnow
from flower.services.commands import sweep_commands
from test_device_chain import water


def completed_late(system):
    cid = water(system).json()["id"]
    now = utcnow()
    start = now - timedelta(minutes=20)
    finished = start + timedelta(minutes=6)
    with system["app"].state.sessions.begin() as db:
        command = db.get(Command, cid)
        command.status = "executing"
        command.started_at = start
        command.session_deadline_at = start + timedelta(minutes=15)
        sweep_commands(db, now)
    payload = dict(
        status="succeeded",
        actual_ml=10,
        finished_at=finished.isoformat(),
        pulses=[
            dict(pulse=1, estimated_ml=10, finished_at=(start + timedelta(seconds=4)).isoformat())
        ],
    )
    return cid, payload


def test_late_verified_result_is_acknowledged_without_rewriting_timeout(system):
    cid, payload = completed_late(system)
    url = f"/api/v1/device/commands/{cid}/result"
    for _ in range(2):
        response = system["client"].post(url, headers=system["device_headers"], json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "timed_out"
    with system["app"].state.sessions() as db:
        session = db.scalar(select(WateringSession).where(WateringSession.command_id == cid))
        assert session.reconciled
        assert session.quota_ml == 10


def test_receipt_reconciliation_verifies_command_pulses_and_time(system):
    cid, payload = completed_late(system)
    invalid = payload | {"actual_ml": 0}
    response = system["client"].post(
        "/api/v1/device/quota/reconcile",
        headers=system["device_headers"],
        json={"used_24h_ml": 20, "receipts": [{"command_id": cid, "result": invalid}]},
    )
    assert response.status_code == 200
    assert response.json()["verified_receipts"] == []
    response = system["client"].post(
        "/api/v1/device/quota/reconcile",
        headers=system["device_headers"],
        json={"used_24h_ml": 20, "receipts": [{"command_id": cid, "result": payload}]},
    )
    assert response.status_code == 200
    assert response.json()["verified_receipts"][0]["command_id"] == cid
    assert response.json()["verified_cloud_used"] == 10


def test_fallback_receipt_creates_one_audit_session(system):
    from flower.models import FallbackPolicy
    from flower.services.care import issue_fallback
    from flower.models import Plant, CareProfile

    with system["app"].state.sessions.begin() as db:
        plant = db.get(Plant, system["plant_id"])
        profile = db.scalar(select(CareProfile).where(CareProfile.plant_id == plant.id))
        issue_fallback(db, system["settings"], plant, profile)
        policy = db.scalar(
            select(FallbackPolicy).where(FallbackPolicy.device_id == plant.device_id)
        )
        version, dose = policy.policy_version, policy.policy["pulse_ml"]
    now = utcnow()
    event = {
        "event_id": "fallback-session",
        "event_type": "local_fallback",
        "source_type": "mock",
        "occurred_at": now.isoformat(),
        "human_readable": "Mock fallback",
        "event_data": {
            "policy_version": version,
            "reserved_ml": dose,
            "result": {
                "status": "succeeded",
                "actual_ml": dose,
                "finished_at": now.isoformat(),
                "pulses": [{"pulse": 1, "estimated_ml": dose, "finished_at": now.isoformat()}],
            },
        },
    }
    for _ in range(2):
        response = system["client"].post(
            "/api/v1/device/events/batch",
            headers=system["device_headers"],
            json={"events": [event]},
        )
        assert response.status_code == 200
    with system["app"].state.sessions() as db:
        rows = list(
            db.scalars(
                select(WateringSession).where(WateringSession.local_id == "fallback-session")
            )
        )
        assert len(rows) == 1
        assert rows[0].quota_ml == dose
