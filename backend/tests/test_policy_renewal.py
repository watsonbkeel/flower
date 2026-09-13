from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import select

from flower.models import CareProfile, Device, FallbackPolicy, utcnow
from flower_pi.policy.fallback import Policy


def test_policy_renews_before_expiry_and_remains_pi_valid(system, monkeypatch):
    from flower.services.care import renew_fallback_policies

    instant = [utcnow()]
    monkeypatch.setattr("flower.services.care.utcnow", lambda: instant[0])
    sessions = system["app"].state.sessions
    with sessions.begin() as db:
        assert renew_fallback_policies(db, system["settings"]) == 1
        assert renew_fallback_policies(db, system["settings"]) == 0
        first = db.scalar(select(FallbackPolicy))
        first_id, first_expiry = first.id, first.valid_until
    instant[0] = first_expiry - timedelta(hours=1)
    with sessions.begin() as db:
        assert renew_fallback_policies(db, system["settings"]) == 1
        assert renew_fallback_policies(db, system["settings"]) == 0
        current = db.scalar(select(FallbackPolicy).order_by(FallbackPolicy.policy_version.desc()))
        assert current.policy_version == 2
        assert current.valid_until == instant[0] + timedelta(days=7)
        Policy.model_validate(current.policy).verify(current.policy_hash, 1)
        assert db.get(FallbackPolicy, first_id).valid_until <= instant[0]


@pytest.mark.parametrize("blocked", ["unconfirmed", "expired", "revoked"])
def test_policy_renewal_requires_valid_confirmed_care_and_active_device(system, blocked):
    from flower.services.care import renew_fallback_policies

    with system["app"].state.sessions.begin() as db:
        if blocked == "unconfirmed":
            db.scalar(select(CareProfile)).confirmed = False
        elif blocked == "expired":
            db.scalar(select(CareProfile)).valid_until = utcnow() - timedelta(seconds=1)
        else:
            db.get(Device, system["device_id"]).revoked = True
        db.flush()
        assert renew_fallback_policies(db, system["settings"]) == 0
        assert db.scalar(select(FallbackPolicy)) is None


def test_short_remaining_care_validity_does_not_cause_renewal_loop(system):
    from flower.services.care import renew_fallback_policies

    with system["app"].state.sessions.begin() as db:
        profile = db.scalar(select(CareProfile))
        profile.valid_until = utcnow() + timedelta(minutes=30)
        db.flush()
        assert renew_fallback_policies(db, system["settings"]) == 1
        for _ in range(3):
            assert renew_fallback_policies(db, system["settings"]) == 0
        assert db.scalar(select(FallbackPolicy)).valid_until == profile.valid_until


def test_concurrent_renewal_issues_only_one_version(system):
    from flower.services.care import renew_fallback_policies

    if system["app"].state.engine.dialect.name != "postgresql":
        pytest.skip("Production row locking requires PostgreSQL")
    barrier = Barrier(2)

    def renew(_):
        with system["app"].state.sessions.begin() as db:
            barrier.wait(timeout=10)
            return renew_fallback_policies(db, system["settings"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(renew, range(2))) == 1
    with system["app"].state.sessions() as db:
        assert len(list(db.scalars(select(FallbackPolicy)))) == 1
