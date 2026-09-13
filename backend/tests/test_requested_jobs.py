from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import select, func

from flower.errors import DomainError
from flower.models import Job, CareProfile, utcnow
from flower.services.jobs import enqueue_job
from flower.services.providers import MockProviders
from flower.worker import Worker


@pytest.mark.parametrize("kind", ["care", "memory"])
def test_new_request_can_retry_failure_while_original_request_remains_idempotent(system, kind):
    client, headers = system["client"], system["user_headers"]
    if kind == "care":
        path = f"/api/v1/plants/{system['plant_id']}/care-profile/generate"
    else:
        memory = client.post(
            "/api/v1/memories",
            headers=headers,
            json={
                "plant_id": system["plant_id"],
                "title": "Family",
                "original_experience": "Small portions",
            },
        ).json()
        path = f"/api/v1/memories/{memory['id']}/structure-rule"
    first = client.post(path, headers=headers | {"Idempotency-Key": "first"}).json()["job_id"]

    class Unavailable(MockProviders):
        def search(self, plant):
            raise DomainError("PROVIDER_UNAVAILABLE")

        def structure_memory(self, text):
            raise DomainError("PROVIDER_UNAVAILABLE")

    worker = Worker(system["app"].state.sessions, system["settings"])
    worker.providers = Unavailable()
    for _ in range(3):
        assert worker.run_once()
        with system["app"].state.sessions.begin() as db:
            db.get(Job, first).available_at = utcnow() - timedelta(seconds=1)
    assert client.get(f"/api/v1/jobs/{first}", headers=headers).json()["status"] == "failed"
    assert (
        client.post(path, headers=headers | {"Idempotency-Key": "first"}).json()["job_id"] == first
    )
    second = client.post(path, headers=headers | {"Idempotency-Key": "retry"}).json()["job_id"]
    assert second != first
    worker.providers = MockProviders()
    assert worker.run_once()
    assert client.get(f"/api/v1/jobs/{second}", headers=headers).json()["status"] == "succeeded"
    assert (
        client.post(path, headers=headers | {"Idempotency-Key": "retry"}).json()["job_id"] == second
    )


def test_care_can_be_regenerated_without_changing_species_or_auto_mode(system):
    client, headers = system["client"], system["user_headers"]
    path = f"/api/v1/plants/{system['plant_id']}/care-profile/generate"
    worker = Worker(system["app"].state.sessions, system["settings"])
    ids = []
    for _ in range(2):
        ids.append(client.post(path, headers=headers).json()["job_id"])
        assert worker.run_once()
    assert ids[0] != ids[1]
    with system["app"].state.sessions() as db:
        profiles = list(db.scalars(select(CareProfile).order_by(CareProfile.version)))
        assert [profile.version for profile in profiles] == [1, 2, 3]
        assert [profile.confirmed for profile in profiles] == [True, False, False]


def test_concurrent_enqueue_same_request_creates_one_durable_job(system):
    barrier = Barrier(8)

    def submit(_):
        with system["app"].state.sessions.begin() as db:
            barrier.wait(timeout=10)
            return enqueue_job(
                db,
                "care_research",
                "plant",
                system["plant_id"],
                system["user_id"],
                "concurrent-request",
            ).id

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(submit, range(8)))
    assert len(set(ids)) == 1
    with system["app"].state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Job)) == 1
