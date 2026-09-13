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
