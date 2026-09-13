from concurrent.futures import ThreadPoolExecutor
import time

import pytest
from sqlalchemy import select, text

from flower.models import Memory
from flower.services.care import refresh_fallback_for_plant
from flower.worker import Worker
from test_memory_policy_lifecycle import enabled_memory, policy


def wait_for_lock(engine, blocker, future):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            if connection.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE :pid = ANY(pg_blocking_pids(pid)))"
                ),
                {"pid": blocker},
            ):
                return
        if future.done():
            future.result()
            pytest.fail("Mutation completed while its memory was locked")
        time.sleep(0.01)
    pytest.fail("Mutation did not reach the contested row")


@pytest.mark.parametrize("mutation", ["edit", "restructure"])
def test_memory_mutation_rechecks_concurrently_enabled_rule(system, mutation):
    engine, sessions = system["app"].state.engine, system["app"].state.sessions
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row lock contention test")
    client, headers = system["client"], system["user_headers"]
    mid = enabled_memory(system)
    client.put(f"/api/v1/memories/{mid}/enabled", headers=headers, json={"enabled": False})
    with sessions.begin() as db:
        db.get(Memory, mid).structured_rule = db.get(Memory, mid).structured_rule | {
            "threshold_shift_pct": -1
        }
    worker = Worker(sessions, system["settings"])
    if mutation == "restructure":
        client.post(f"/api/v1/memories/{mid}/structure-rule", headers=headers)
        claim = worker.acquire()

    def mutate():
        if mutation == "restructure":
            return worker.perform(claim)
        return client.put(
            f"/api/v1/memories/{mid}",
            headers=headers,
            json={
                "title": "Edited",
                "plant_id": system["plant_id"],
                "original_experience": "Unconfirmed replacement",
            },
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        with sessions.begin() as db:
            memory = db.scalar(select(Memory).where(Memory.id == mid).with_for_update())
            memory.rule_enabled = True
            refresh_fallback_for_plant(db, system["settings"], memory.plant_id)
            blocker = db.scalar(text("SELECT pg_backend_pid()"))
            future = pool.submit(mutate)
            wait_for_lock(engine, blocker, future)
        result = future.result(timeout=10)
    assert result is True if mutation == "restructure" else result.status_code == 200
    with sessions() as db:
        memory = db.get(Memory, mid)
        assert not memory.rule_enabled
        assert not memory.rule_confirmed
    assert policy(system)["pulse_ml"] == 10


def test_enable_rejects_rule_removed_by_concurrent_edit(system):
    engine, sessions = system["app"].state.engine, system["app"].state.sessions
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row lock contention test")
    client, headers = system["client"], system["user_headers"]
    mid = enabled_memory(system)
    client.put(f"/api/v1/memories/{mid}/enabled", headers=headers, json={"enabled": False})
    with ThreadPoolExecutor(max_workers=1) as pool:
        with sessions.begin() as db:
            memory = db.scalar(select(Memory).where(Memory.id == mid).with_for_update())
            memory.original_experience = "Unconfirmed replacement"
            memory.structured_rule, memory.rule_confirmed = None, False
            refresh_fallback_for_plant(db, system["settings"], memory.plant_id)
            blocker = db.scalar(text("SELECT pg_backend_pid()"))
            future = pool.submit(
                client.put,
                f"/api/v1/memories/{mid}/enabled",
                headers=headers,
                json={"enabled": True, "confirmed": True},
            )
            wait_for_lock(engine, blocker, future)
        result = future.result(timeout=10)
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "MEMORY_CONFIRMATION_REQUIRED"
    with sessions() as db:
        memory = db.get(Memory, mid)
        assert not memory.rule_enabled and not memory.rule_confirmed
        assert memory.structured_rule is None
    assert policy(system)["pulse_ml"] == 10
