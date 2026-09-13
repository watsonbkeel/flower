from sqlalchemy import select

from flower.models import CareProfile, Plant, Memory, Event, Device
from flower.worker import Worker


def test_care_job_sources_confirmation_and_fallback(system):
    client, headers, pid = system["client"], system["user_headers"], system["plant_id"]
    response = client.post(f"/api/v1/plants/{pid}/care-profile/generate", headers=headers)
    assert response.status_code == 202
    assert Worker(system["app"].state.sessions, system["settings"]).run_once()
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}", headers=headers).json()
    assert job["status"] == "succeeded"
    profile_id = job["result"]["profile_id"]
    with system["app"].state.sessions() as db:
        profile = db.get(CareProfile, profile_id)
        assert not profile.confirmed
        assert len(profile.profile["sources"]) >= 2
        assert profile.profile["source_type"] == "mock"
    confirm = client.post(
        f"/api/v1/plants/{pid}/care-profile/confirm",
        headers=headers,
        json={"profile_id": profile_id},
    )
    assert confirm.status_code == 200
    policy = client.get("/api/v1/device/fallback-policy", headers=system["device_headers"])
    assert policy.status_code == 200
    assert policy.json()["policy"]["timezone"] == "Asia/Shanghai"


def test_memory_needs_explicit_confirmation_and_records_effect(system):
    client, headers = system["client"], system["user_headers"]
    created = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "plant_id": system["plant_id"],
            "title": "Grandfather",
            "story": "Family garden",
            "original_experience": "Evening small portions",
        },
    )
    assert created.status_code == 201
    memory_id = created.json()["id"]
    assert (
        client.put(
            f"/api/v1/memories/{memory_id}/enabled",
            headers=headers,
            json={"enabled": True, "confirmed": False},
        ).status_code
        == 409
    )
    job = client.post(f"/api/v1/memories/{memory_id}/structure-rule", headers=headers)
    assert job.status_code == 202
    assert Worker(system["app"].state.sessions, system["settings"]).run_once()
    assert (
        client.put(
            f"/api/v1/memories/{memory_id}/enabled",
            headers=headers,
            json={"enabled": True, "confirmed": True},
        ).status_code
        == 200
    )
    from flower.services.care import evaluate_plant

    with system["app"].state.sessions.begin() as db:
        result = evaluate_plant(
            db, system["settings"], db.get(Plant, system["plant_id"]), create=False
        )
        assert result["memory_effects"]
    with system["app"].state.sessions() as db:
        event = db.scalar(select(Event).where(Event.event_type == "memory_rule_applied"))
        assert event.source_type == "mock"
        assert db.get(Memory, memory_id).applied_count == 0


def test_auto_mode_cannot_enable_without_calibration(system):
    with system["app"].state.sessions.begin() as db:
        db.get(Device, system["device_id"]).calibration = {}
    response = system["client"].put(
        f"/api/v1/plants/{system['plant_id']}/auto-mode",
        headers=system["user_headers"],
        json={"enabled": True},
    )
    assert response.status_code == 409
