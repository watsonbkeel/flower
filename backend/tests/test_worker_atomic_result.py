from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from flower.models import (
    Alert,
    CareProfile,
    Device,
    FallbackPolicy,
    Job,
    Memory,
    PlantImage,
    utcnow,
)
from flower.schemas import serialize
from flower.services.alerts import alert
from flower.services.providers import MockProviders
from flower.worker import Worker


def prepare_job(system, kind):
    client, headers, pid = system["client"], system["user_headers"], system["plant_id"]
    if kind == "care_research":
        return client.post(f"/api/v1/plants/{pid}/care-profile/generate", headers=headers).json()[
            "job_id"
        ]
    if kind == "memory_structure":
        from test_memory_policy_lifecycle import enabled_memory

        mid = enabled_memory(system)
        return client.post(f"/api/v1/memories/{mid}/structure-rule", headers=headers).json()[
            "job_id"
        ]
    if kind == "plant_recognition":
        from test_jobs_images import upload

        return upload(system).json()["job_id"]
    with system["app"].state.sessions.begin() as db:
        if kind == "weather_refresh":
            from flower.services.weather import schedule_weather

            schedule_weather(db, utcnow())
        else:
            alert(db, db.get(Device, system["device_id"]), "LOW_WATER", "Test alert")
        return db.scalar(select(Job.id).where(Job.job_type == kind))


def business_snapshot(system):
    with system["app"].state.sessions() as db:
        return {
            model.__tablename__: [
                serialize(item) for item in db.scalars(select(model).order_by(model.id))
            ]
            for model in [Alert, CareProfile, FallbackPolicy, Memory, PlantImage]
        }


@pytest.mark.parametrize(
    "kind",
    [
        "care_research",
        "memory_structure",
        "weather_refresh",
        "plant_recognition",
        "alert_notification",
    ],
)
def test_expiry_at_result_commit_rolls_back_all_business_changes(system, monkeypatch, kind):
    jid = prepare_job(system, kind)

    class SimulatedSent(MockProviders):
        def notify(self, message):
            return {"status": "sent", "source_type": "real"}

    worker = Worker(system["app"].state.sessions, system["settings"])
    worker.providers = SimulatedSent()
    claim = worker.acquire()
    assert claim["id"] == jid
    before = business_snapshot(system)
    deadline = datetime.fromisoformat(claim["locked_at"]) + timedelta(seconds=claim["timeout_sec"])
    monkeypatch.setattr("flower.services.jobs.utcnow", lambda: deadline)
    assert worker.perform(claim) is False
    assert business_snapshot(system) == before
    with system["app"].state.sessions() as db:
        job = db.get(Job, jid)
        assert job.status == "running" and job.result is None
    monkeypatch.setattr("flower.services.jobs.utcnow", utcnow)
    from flower.services.jobs import recover_jobs

    with system["app"].state.sessions.begin() as db:
        recover_jobs(db, deadline)
        db.get(Job, jid).available_at = utcnow() - timedelta(seconds=1)
    assert worker.run_once()
    with system["app"].state.sessions() as db:
        assert db.get(Job, jid).status == "succeeded"
        assert db.get(Job, jid).attempt == 2


def test_already_expired_notification_does_not_call_provider(system, monkeypatch):
    prepare_job(system, "alert_notification")
    worker = Worker(system["app"].state.sessions, system["settings"])
    claim = worker.acquire()
    deadline = datetime.fromisoformat(claim["locked_at"]) + timedelta(seconds=claim["timeout_sec"])
    calls = []

    class Recording(MockProviders):
        def notify(self, message):
            calls.append(message)
            return super().notify(message)

    worker.providers = Recording()
    monkeypatch.setattr("flower.worker.utcnow", lambda: deadline)
    assert worker.perform(claim) is False
    assert calls == []
