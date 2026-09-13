from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from flower.models import CareProfile, utcnow
from flower.worker import Worker


def enabled_memory(system):
    client, headers = system["client"], system["user_headers"]
    item = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "title": "Family",
            "plant_id": system["plant_id"],
            "original_experience": "Evening small portions",
        },
    ).json()
    client.post(f"/api/v1/memories/{item['id']}/structure-rule", headers=headers)
    assert Worker(system["app"].state.sessions, system["settings"]).run_once()
    assert (
        client.put(
            f"/api/v1/memories/{item['id']}/enabled",
            headers=headers,
            json={"enabled": True, "confirmed": True},
        ).status_code
        == 200
    )
    return item["id"]


def policy(system):
    result = system["client"].get(
        "/api/v1/device/fallback-policy", headers=system["device_headers"]
    )
    assert result.status_code == 200
    return result.json()["policy"]


@pytest.mark.parametrize("change", ["edit", "detach", "restructure"])
def test_removing_confirmed_memory_rule_recompiles_fallback(system, change):
    client, headers = system["client"], system["user_headers"]
    mid = enabled_memory(system)
    before = policy(system)
    assert before["pulse_ml"] == 5
    if change == "restructure":
        client.post(f"/api/v1/memories/{mid}/structure-rule", headers=headers)
        assert Worker(system["app"].state.sessions, system["settings"]).run_once()
    else:
        assert (
            client.put(
                f"/api/v1/memories/{mid}",
                headers=headers,
                json={
                    "title": "Edited",
                    "plant_id": None if change == "detach" else system["plant_id"],
                    "original_experience": "New unconfirmed experience",
                },
            ).status_code
            == 200
        )
    after = policy(system)
    assert after["policy_version"] > before["policy_version"]
    assert after["pulse_ml"] == 10
    assert after["allowed_windows_local"] == [["06:00", "09:00"], ["17:00", "20:00"]]


def test_fallback_cannot_outlive_its_confirmed_care_profile(system):
    until = utcnow() + timedelta(minutes=30)
    with system["app"].state.sessions.begin() as db:
        db.scalar(select(CareProfile)).valid_until = until
    enabled_memory(system)
    assert datetime.fromisoformat(policy(system)["valid_until"]) <= until


def test_memory_change_with_expired_care_revokes_instead_of_issuing_policy(system):
    mid = enabled_memory(system)
    with system["app"].state.sessions.begin() as db:
        db.scalar(select(CareProfile)).valid_until = utcnow() - timedelta(seconds=1)
    response = system["client"].put(
        f"/api/v1/memories/{mid}/enabled",
        headers=system["user_headers"],
        json={"enabled": False, "confirmed": False},
    )
    assert response.status_code == 200
    assert (
        system["client"]
        .get("/api/v1/device/fallback-policy", headers=system["device_headers"])
        .status_code
        == 404
    )
