from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import select

from flower.models import CareProfile, FallbackPolicy, Job, Plant, utcnow
from flower.services.providers import MockProviders
from flower.worker import Worker


SPECIES = {
    "common_name": "Gardenia",
    "scientific_name": "Gardenia jasminoides",
    "input_method": "manual",
}


def test_changed_species_cannot_reconfirm_old_care_or_water_until_new_research(system):
    client, headers, pid = system["client"], system["user_headers"], system["plant_id"]
    with system["app"].state.sessions() as db:
        old_id = db.scalar(select(CareProfile.id).where(CareProfile.plant_id == pid))
    assert (
        client.post(
            f"/api/v1/plants/{pid}/confirm-species", headers=headers, json=SPECIES
        ).status_code
        == 200
    )
    rejected = client.post(
        f"/api/v1/plants/{pid}/care-profile/confirm", headers=headers, json={"profile_id": old_id}
    )
    assert rejected.status_code == 409
    assert (
        client.put(
            f"/api/v1/plants/{pid}/auto-mode", headers=headers, json={"enabled": True}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/plants/{pid}/water",
            headers=headers | {"Idempotency-Key": "old-card"},
            json={"quantity": 10, "unit": "ml"},
        ).status_code
        == 409
    )
    with system["app"].state.sessions() as db:
        old = db.get(CareProfile, old_id)
        assert not old.confirmed and old.valid_until <= utcnow()
        assert db.scalar(select(FallbackPolicy)) is None
    job = client.post(f"/api/v1/plants/{pid}/care-profile/generate", headers=headers).json()
    assert Worker(system["app"].state.sessions, system["settings"]).run_once()
    result = client.get(f"/api/v1/jobs/{job['job_id']}", headers=headers).json()
    assert result["status"] == "succeeded"
    assert (
        client.post(
            f"/api/v1/plants/{pid}/care-profile/confirm",
            headers=headers,
            json={"profile_id": result["result"]["profile_id"]},
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/v1/plants/{pid}/auto-mode", headers=headers, json={"enabled": True}
        ).status_code
        == 200
    )


def test_species_change_during_research_rejects_old_worker_result(system):
    client, headers, pid = system["client"], system["user_headers"], system["plant_id"]
    job_id = client.post(f"/api/v1/plants/{pid}/care-profile/generate", headers=headers).json()[
        "job_id"
    ]

    class ChangingSpecies(MockProviders):
        def search(self, plant):
            assert (
                client.post(
                    f"/api/v1/plants/{pid}/confirm-species", headers=headers, json=SPECIES
                ).status_code
                == 200
            )
            return super().search(plant)

    worker = Worker(system["app"].state.sessions, system["settings"])
    worker.providers = ChangingSpecies()
    worker.run_once()
    with system["app"].state.sessions() as db:
        assert db.get(Job, job_id).status != "succeeded"
        assert len(list(db.scalars(select(CareProfile)))) == 1
        assert not db.scalar(select(CareProfile)).confirmed


def test_concurrent_species_and_care_confirmation_leave_old_profile_invalid(system):
    client, headers, pid = system["client"], system["user_headers"], system["plant_id"]
    with system["app"].state.sessions.begin() as db:
        profile = db.scalar(select(CareProfile))
        profile.confirmed = False
        old_id = profile.id
    barrier = Barrier(2)

    def change():
        barrier.wait(timeout=10)
        return client.post(f"/api/v1/plants/{pid}/confirm-species", headers=headers, json=SPECIES)

    def confirm():
        barrier.wait(timeout=10)
        return client.post(
            f"/api/v1/plants/{pid}/care-profile/confirm",
            headers=headers,
            json={"profile_id": old_id},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        changed, confirmed = pool.submit(change), pool.submit(confirm)
        assert changed.result(timeout=15).status_code == 200
        assert confirmed.result(timeout=15).status_code in {200, 409}
    with system["app"].state.sessions() as db:
        assert not db.get(Plant, pid).auto_mode
        assert not db.get(CareProfile, old_id).confirmed
        assert db.get(CareProfile, old_id).valid_until <= utcnow()
        assert all(policy.valid_until <= utcnow() for policy in db.scalars(select(FallbackPolicy)))
