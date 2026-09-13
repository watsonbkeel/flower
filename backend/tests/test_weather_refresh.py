from datetime import timedelta

import pytest
from sqlalchemy import select

from flower.errors import DomainError
from flower.models import CareProfile, Job, Plant, utcnow
from flower.services.providers import MockProviders
from flower.worker import Worker


def active_profile(db, system):
    return db.scalar(select(CareProfile).where(CareProfile.plant_id == system["plant_id"]))


def test_weather_refresh_is_scheduled_once_and_renews_after_expiry(system):
    from flower.services.weather import schedule_weather

    sessions = system["app"].state.sessions
    now = utcnow()
    with sessions.begin() as db:
        schedule_weather(db, now)
        schedule_weather(db, now)
        jobs = list(db.scalars(select(Job)))
        assert len(jobs) == 1
        assert jobs[0].job_type == "weather_refresh"
    worker = Worker(sessions, system["settings"])
    assert worker.run_once(isolated=True)
    with sessions.begin() as db:
        job = db.scalar(select(Job))
        assert job.status == "succeeded"
        profile = active_profile(db, system)
        assert profile.profile["weather"]["source_type"] == "mock"
        assert profile.confirmed and profile.version == 1
        schedule_weather(db, now + timedelta(minutes=1))
        assert len(list(db.scalars(select(Job)))) == 1
        schedule_weather(db, now + timedelta(hours=4))
        assert len(list(db.scalars(select(Job)))) == 2


def test_weather_failure_uses_existing_bounded_job_retry_and_retains_cache(system):
    from flower.services.weather import schedule_weather

    sessions = system["app"].state.sessions
    old = MockProviders().weather({})
    old["valid_until"] = (utcnow() - timedelta(seconds=1)).isoformat()
    old["observed_at"] = (utcnow() - timedelta(hours=4)).isoformat()
    with sessions.begin() as db:
        profile = active_profile(db, system)
        profile.profile = profile.profile | {"weather": old}
        schedule_weather(db, utcnow())

    class Unavailable(MockProviders):
        def weather(self, plant):
            raise DomainError("PROVIDER_UNAVAILABLE")

    worker = Worker(sessions, system["settings"])
    worker.providers = Unavailable()
    for attempt in range(1, 4):
        assert worker.run_once()
        with sessions.begin() as db:
            job = db.scalar(select(Job))
            assert job.attempt == attempt
            assert job.status == ("failed" if attempt == 3 else "queued")
            job.available_at = utcnow() - timedelta(seconds=1)
            assert active_profile(db, system).profile["weather"] == old


@pytest.mark.parametrize("change", ["revoked", "location"])
def test_weather_refresh_cannot_update_a_changed_profile(system, change):
    from flower.services.weather import schedule_weather

    sessions = system["app"].state.sessions
    with sessions.begin() as db:
        schedule_weather(db, utcnow())

    class ChangingProfile(MockProviders):
        def weather(self, plant):
            with sessions.begin() as db:
                if change == "revoked":
                    active_profile(db, system).confirmed = False
                else:
                    db.get(Plant, system["plant_id"]).city = "Beijing"
            return super().weather(plant)

    worker = Worker(sessions, system["settings"])
    worker.providers = ChangingProfile()
    worker.run_once()
    with sessions() as db:
        assert "weather" not in active_profile(db, system).profile
        assert db.scalar(select(Job)).status != "succeeded"


@pytest.mark.parametrize("invalid", ["expired", "future", "source", "malformed", None])
def test_only_current_matching_weather_affects_rain_decision(system, invalid):
    from flower.services.care import evaluate_plant
    from flower.models import DeviceStatus

    now = utcnow()
    weather = MockProviders().weather({})
    weather["rain_next_12h_mm"] = 10
    if invalid == "expired":
        weather["valid_until"] = (now - timedelta(seconds=1)).isoformat()
    elif invalid == "future":
        weather["observed_at"] = (now + timedelta(hours=1)).isoformat()
    elif invalid == "source":
        weather["source_type"] = "real"
    elif invalid == "malformed":
        weather["valid_until"] = "invalid"
    with system["app"].state.sessions.begin() as db:
        profile = active_profile(db, system)
        profile.profile = profile.profile | {"weather": weather}
        plant = db.get(Plant, system["plant_id"])
        plant.placement_type = "outdoor"
        db.get(DeviceStatus, plant.device_id).soil_moisture = 39
        result = evaluate_plant(db, system["settings"], plant, create=False)
        if invalid is None:
            assert result["decision"] == "defer"
            assert result["reason"] == "rain_expected"
        else:
            assert result["reason"] in {"outside_window", "within_window_below_target"}


@pytest.mark.parametrize("invalid", ["unconfirmed", "expired"])
def test_inactive_care_profiles_do_not_schedule_weather(system, invalid):
    from flower.services.weather import schedule_weather

    with system["app"].state.sessions.begin() as db:
        profile = active_profile(db, system)
        if invalid == "unconfirmed":
            profile.confirmed = False
        else:
            profile.valid_until = utcnow() - timedelta(seconds=1)
        db.flush()
        schedule_weather(db, utcnow())
        assert db.scalar(select(Job)) is None
