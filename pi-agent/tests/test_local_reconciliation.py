from datetime import timedelta
import pytest

from test_executor import setup_executor
from test_safety import NOW


def test_provisional_reconcile_requires_identical_durable_receipt(tmp_path):
    executor, cmd, pump, clock, states, ledger = setup_executor(tmp_path)
    result = executor.execute(cmd)
    with ledger.connection:
        ledger.connection.execute(
            "UPDATE water_ledger SET state='provisional',quota_ml=reserved_ml"
        )
    forged = {"command_id": cmd.id, "result": result | {"actual_ml": 0}}
    with pytest.raises(ValueError):
        ledger.reconcile_receipt(forged, NOW + timedelta(hours=1))
    assert ledger.get(cmd.id)["state"] == "provisional"
    assert ledger.reconcile_receipt(
        {"command_id": cmd.id, "result": result}, NOW + timedelta(hours=1)
    )
    assert ledger.get(cmd.id)["state"] == "reconciled"
    assert ledger.receipts() == []


def test_no_receipt_cannot_release_quota(tmp_path):
    executor, cmd, pump, clock, states, ledger = setup_executor(tmp_path)
    ledger.reserve(cmd.id, cmd.source, 20, NOW, "boot", 0, limit_ml=120, interval_hours=6)
    ledger.provisional(cmd.id)
    with pytest.raises(ValueError):
        ledger.reconcile_receipt({"command_id": cmd.id, "result": {"actual_ml": 0}}, NOW)
    assert ledger.used(NOW) == 20


def test_fallback_receipts_do_not_starve_cloud_reconciliation(tmp_path):
    from flower_pi.storage.ledger import Ledger

    ledger = Ledger(tmp_path / "history.db")
    for index in range(101):
        command_id = f"fallback-{index:03}"
        at = NOW + timedelta(hours=12 * index)
        ledger.reserve(
            command_id, "local_fallback", 10, at, "boot", index, limit_ml=120, interval_hours=6
        )
        ledger.finish(command_id, actual_ml=10, now=at, monotonic=index, verified=True)
        ledger.set_value("receipt:" + command_id, {"status": "succeeded", "actual_ml": 10})
    at = NOW + timedelta(days=60)
    ledger.reserve("remote", "user_manual", 10, at, "boot", 200, limit_ml=120, interval_hours=6)
    ledger.set_value("receipt:remote", {"status": "succeeded", "actual_ml": 10})
    assert [receipt["command_id"] for receipt in ledger.receipts()] == ["remote"]
    assert ledger.used(at) == 10
    ledger.close()
