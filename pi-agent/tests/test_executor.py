from datetime import timedelta
from dataclasses import replace

import pytest

from flower_pi.actuators.pump import MockPump
from flower_pi.commands.executor import Executor, DispenseCommand
from flower_pi.calibration import validate_measurements
from flower_pi.storage.ledger import Ledger
from flower_pi.state import DeviceState
from test_safety import NOW


class Clock:
    def __init__(self):
        self.seconds = 0
        self.callback = None

    def monotonic(self):
        return self.seconds

    def utcnow(self):
        return NOW + timedelta(seconds=self.seconds)

    def sleep(self, seconds):
        self.seconds += seconds
        if self.callback:
            self.callback()


def setup_executor(tmp_path, **changes):
    clock = Clock()
    pump = MockPump()
    state = DeviceState(operating_mode="FULL", activity="IDLE", water_level_ok=True,
                        soil_pct=20, time_trusted=True, calibration_valid=True,
                        profile_valid=True, fault_codes=())
    states = [state]
    ledger = Ledger(tmp_path / "state.db")
    calibration = validate_measurements([30, 30, 30], [1, 1, 1], 1,
                                        20000, 10000, "4cm", NOW)
    executor = Executor("device1", pump, ledger, lambda: states[0], calibration, clock)
    command = DispenseCommand(**(dict(id="c1", device_id="device1", source="cloud_auto",
        run_mode="real", target_ml=20, pulse_ml=10, max_pulses=2,
        max_continuous_sec=10, afterdrip_settle_sec=30, absorb_wait_sec=300,
        session_max_duration_sec=900, claim_deadline_at=NOW + timedelta(seconds=60),
        stop_soil_pct=40) | changes))
    return executor, command, pump, clock, states, ledger


def test_long_session_ignores_claim_ttl_after_started(tmp_path):
    executor, cmd, pump, clock, states, ledger = setup_executor(tmp_path)
    result = executor.execute(cmd)
    assert result["status"] == "succeeded"
    assert clock.seconds > 60
    assert pump.starts == 2
    assert not pump.commanded_on
    assert ledger.get("c1")["quota_ml"] == 20
    assert executor.execute(cmd)["status"] == "failed"
    assert pump.starts == 2


@pytest.mark.parametrize("fault", ["water", "soil", "clock", "mode", "exception"])
def test_fault_during_pulse_closes_and_keeps_reservation(tmp_path, fault):
    executor, cmd, pump, clock, states, ledger = setup_executor(tmp_path)
    def inject():
        if clock.seconds >= 0.2:
            if fault == "exception":
                raise OSError("injected sensor disconnection")
            fields = {"water": {"water_level_ok": False}, "soil": {"soil_pct": None},
                      "clock": {"time_trusted": False}, "mode": {"operating_mode": "SAFE_HOLD"}}[fault]
            states[0] = replace(states[0], **fields)
    clock.callback = inject
    result = executor.execute(cmd)
    assert result["status"] == "failed"
    assert not pump.commanded_on
    assert pump.starts == 1
    assert ledger.get("c1")["state"] == "provisional"
    assert ledger.used(NOW) == 20


def test_session_deadline_checked_during_wait(tmp_path):
    executor, cmd, pump, clock, states, ledger = setup_executor(tmp_path, session_max_duration_sec=100)
    result = executor.execute(cmd)
    assert result["status"] == "timed_out"
    assert clock.seconds <= 100.1
    assert pump.starts == 1
    assert not pump.commanded_on


def test_closed_loop_stops_after_target_and_reserves_before_open(tmp_path):
    executor, cmd, pump, clock, states, ledger = setup_executor(tmp_path)
    def sample():
        if pump.commanded_on:
            assert ledger.used(NOW) == 20
        if clock.seconds > 3:
            states[0] = replace(states[0], soil_pct=45)
    clock.callback = sample
    assert executor.execute(cmd)["status"] == "succeeded"
    assert pump.starts == 1
    assert ledger.used(NOW) == 10


@pytest.mark.parametrize("changes", [{"device_id": "other"}, {"pulse_ml": 2},
    {"claim_deadline_at": NOW - timedelta(seconds=1)}, {"source": "maintenance_test"}])
def test_invalid_execution_does_not_touch_pump(tmp_path, changes):
    executor, cmd, pump, clock, states, ledger = setup_executor(tmp_path, **changes)
    assert executor.execute(cmd)["status"] == "failed"
    assert pump.starts == 0


def test_low_water_twenty_commands_no_starts(tmp_path):
    executor, cmd, pump, clock, states, ledger = setup_executor(tmp_path)
    states[0] = replace(states[0], water_level_ok=False)
    for _ in range(20):
        assert executor.execute(cmd)["status"] == "failed"
    assert pump.starts == 0
