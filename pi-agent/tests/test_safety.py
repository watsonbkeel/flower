from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from flower_pi.calibration import Calibration, validate_measurements
from flower_pi.state import DeviceState, ModeTracker
from flower_pi.safety.gate import can_dispense
from flower_pi.storage.ledger import Ledger
from flower_pi.policy.fallback import Policy, policy_digest
from flower_pi.sensors.water_level import WaterLevel
from flower_pi.sensors.soil import SoilFilter

NOW = datetime(2026, 9, 13, 0, tzinfo=timezone.utc)


@pytest.fixture
def state():
    return DeviceState(
        operating_mode="FULL",
        activity="IDLE",
        water_level_ok=True,
        soil_pct=20,
        time_trusted=True,
        calibration_valid=True,
        profile_valid=True,
        fault_codes=(),
    )


@pytest.mark.parametrize("mode", ["STARTING", "SAFE_HOLD"])
@pytest.mark.parametrize(
    "source", ["cloud_auto", "user_manual", "local_fallback", "maintenance_test"]
)
def test_safe_modes_never_dispense(state, mode, source):
    assert not can_dispense(replace(state, operating_mode=mode), source).allowed


@pytest.mark.parametrize(
    "change",
    [
        {"activity": "CAPTURING"},
        {"activity": "WATERING"},
        {"water_level_ok": False},
        {"water_level_ok": None},
        {"soil_pct": None},
        {"soil_pct": float("nan")},
        {"time_trusted": False},
        {"calibration_valid": False},
        {"profile_valid": False},
        {"fault_codes": ("DISK_ERROR",)},
        {"fault_codes": ("PUMP_DRIVER_SUSPECT",)},
        {"fault_codes": ("UNKNOWN_FAULT",)},
    ],
)
def test_every_uncertainty_blocks(state, change):
    assert not can_dispense(replace(state, **change), "user_manual").allowed


def test_sources_and_noncritical_faults(state):
    assert can_dispense(state, "user_manual").allowed
    assert can_dispense(
        replace(state, fault_codes=("BLE_STALE", "CAMERA_UNAVAILABLE")), "cloud_auto"
    ).allowed
    assert not can_dispense(state, "local_fallback", policy_valid=True).allowed
    local = replace(state, operating_mode="LOCAL_CONSERVATIVE", fault_codes=("CLOUD_OFFLINE",))
    assert can_dispense(local, "local_fallback", policy_valid=True).allowed
    assert not can_dispense(local, "cloud_auto").allowed
    assert not can_dispense(local, "local_fallback").allowed
    assert not can_dispense(state, "peripheral").allowed
    assert not can_dispense(state, "maintenance_test").allowed
    assert can_dispense(state, "maintenance_test", local_test=True, test_seconds=1).allowed
    assert not can_dispense(state, "maintenance_test", local_test=True, test_seconds=1.01).allowed


def test_calibration_uses_mean_and_rejects_invalid_measurements():
    c = validate_measurements([35, 36, 37], [1, 2, 3], 1, 20000, 10000, "mark 4cm", NOW)
    assert c.flow_ml_sec == pytest.approx(3.6)
    assert c.afterdrip_mean_ml == 2
    assert c.afterdrip_max_ml == 3
    assert c.min_controllable_ml == pytest.approx(5.6)
    assert c.run_seconds(10) == pytest.approx(8 / 3.6)
    with pytest.raises(ValueError):
        c.run_seconds(2)
    for flow, drip in [([10, 30, 50], [0, 0, 0]), ([35, 36, 37], [1, 2, 4])]:
        with pytest.raises(ValueError):
            validate_measurements(flow, drip, 1, 20000, 10000, "mark", NOW)
    with pytest.raises(ValueError):
        Calibration(
            flow_ml_sec=float("nan"),
            afterdrip_mean_ml=0,
            afterdrip_max_ml=0,
            min_run_sec=1,
            adc_dry=20000,
            adc_wet=10000,
            insert_depth_mark="4cm",
            calibrated_at=NOW,
        )


def test_ledger_reserve_duplicate_crash_and_twenty_restarts(tmp_path):
    path = tmp_path / "ledger.db"
    ledger = Ledger(path)
    ledger.reserve("one", "cloud_auto", 60, NOW, "boot1", 0, limit_ml=120, interval_hours=6)
    assert ledger.used(NOW) == 60
    with pytest.raises(ValueError):
        ledger.reserve("one", "cloud_auto", 60, NOW, "boot1", 0, limit_ml=120, interval_hours=6)
    ledger.close()
    for number in range(20):
        ledger = Ledger(path)
        ledger.recover(NOW + timedelta(minutes=number))
        assert ledger.used(NOW + timedelta(minutes=number)) == 60
        assert ledger.get("one")["state"] == "provisional"
        ledger.close()
    ledger = Ledger(path)
    assert ledger.used(NOW + timedelta(hours=25)) == 0


def test_unknown_timestamp_conservatively_ages_from_first_trusted_recovery(tmp_path):
    ledger = Ledger(tmp_path / "ledger.db")
    ledger.reserve("one", "user_manual", 60, NOW, "boot", 0, limit_ml=120, interval_hours=6)
    ledger.connection.execute(
        "UPDATE water_ledger SET trusted_wall_time_utc=NULL, server_issued_at_utc=NULL"
    )
    ledger.connection.commit()
    ledger.recover(None)
    with pytest.raises(ValueError):
        ledger.used(None)
    ledger.recover(NOW)
    ledger.recover(NOW + timedelta(hours=1))
    assert ledger.used(NOW + timedelta(hours=23)) == 60
    assert ledger.used(NOW + timedelta(hours=25)) == 0


def test_quota_does_not_drop_on_unverified_cloud_reconciliation(tmp_path):
    ledger = Ledger(tmp_path / "ledger.db")
    ledger.reserve("one", "cloud_auto", 60, NOW, "boot", 0, limit_ml=120, interval_hours=6)
    assert ledger.reconcile_used(10, NOW) == (60, True)
    assert ledger.reconcile_used(90, NOW) == (90, True)
    assert ledger.used(NOW) == 90
    with pytest.raises(ValueError):
        ledger.reserve(
            "two",
            "user_manual",
            40,
            NOW + timedelta(hours=7),
            "boot",
            20,
            limit_ml=120,
            interval_hours=6,
        )
    with pytest.raises(ValueError):
        ledger.finish("one", actual_ml=0, now=NOW, monotonic=1, verified=False)


def test_reservation_is_atomic_between_connections(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "ledger.db"
    Ledger(path).close()

    def reserve(number):
        ledger = Ledger(path)
        try:
            ledger.reserve(
                str(number), "user_manual", 60, NOW, "boot", 0, limit_ml=120, interval_hours=6
            )
            return True
        except (ValueError, sqlite3.IntegrityError):
            return False
        finally:
            ledger.close()

    with ThreadPoolExecutor(max_workers=10) as pool:
        assert sum(pool.map(reserve, range(20))) == 1


def test_cloud_quota_observation_cannot_refresh_an_old_high_value_forever(tmp_path):
    ledger = Ledger(tmp_path / "ledger.db")
    ledger.reconcile_used(90, NOW)
    for hour in range(1, 26):
        ledger.reconcile_used(0, NOW + timedelta(hours=hour))
    assert ledger.used(NOW + timedelta(hours=25)) == 0


def make_policy(**changes):
    values = dict(
        policy_version=1,
        profile_version=1,
        generated_at=NOW,
        valid_until=NOW + timedelta(days=7),
        trigger_soil_below_pct=28,
        min_interval_hours=12,
        pulse_ml=10,
        max_pulses=1,
        max_session_ml=10,
        max_24h_ml=60,
        timezone="Asia/Shanghai",
        allowed_windows_local=[["06:00", "09:00"], ["17:00", "20:00"]],
        profile_hash="sha256:" + "a" * 64,
    )
    return Policy(**(values | changes))


@pytest.mark.parametrize(
    "change",
    [
        {"timezone": "Invalid/Zone"},
        {"timezone": ""},
        {"max_pulses": 2},
        {"min_interval_hours": 2},
        {"allowed_windows_local": [["23:00", "01:00"]]},
        {"valid_until": NOW + timedelta(days=8)},
        {"pulse_ml": float("nan")},
    ],
)
def test_invalid_fallback_rejected(change):
    with pytest.raises(ValueError):
        make_policy(**change)


def test_fallback_timezone_hash_version_and_expiry():
    p = make_policy()
    assert p.permits(NOW, soil_pct=20, last_watered=None, used_ml=0)
    assert not p.permits(NOW + timedelta(hours=3), soil_pct=20, last_watered=None, used_ml=0)
    assert not p.permits(NOW + timedelta(days=8), soil_pct=20, last_watered=None, used_ml=0)
    assert not p.permits(NOW, soil_pct=28, last_watered=None, used_ml=0)
    assert not p.permits(NOW, soil_pct=20, last_watered=NOW - timedelta(hours=2), used_ml=0)
    p.verify(policy_digest(p), minimum_version=1)
    with pytest.raises(ValueError):
        p.verify("corrupt", minimum_version=1)
    with pytest.raises(ValueError):
        p.verify(policy_digest(p), minimum_version=2)


def test_water_level_asymmetric_debounce():
    sensor = WaterLevel()
    assert sensor.update(False, 0) is False
    for i in range(1, 52):
        sensor.update(True, i * 0.2)
    assert sensor.ok
    for i in range(4):
        assert sensor.update(False, 10.4 + i * 0.2)
    assert not sensor.update(False, 11.2)
    assert not sensor.update(True, 11.4)
    assert not sensor.update(True, 21.2)
    assert sensor.update(True, 21.4)


def test_soil_median_and_invalid_streak():
    sensor = SoilFilter(20000, 10000)
    assert sensor.update(15000) is None
    assert sensor.update(15000) is None
    assert sensor.update(14900) == 50
    assert sensor.update(10000) == pytest.approx(50.5)
    for _ in range(5):
        sensor.update(None)
    assert sensor.fault
    assert sensor.value is None


def test_operating_mode_hysteresis(state):
    tracker = ModeTracker()
    assert tracker.update(state, now_mono=0, cloud_age=0, policy_valid=True) == "STARTING"
    assert tracker.update(state, now_mono=180, cloud_age=0, policy_valid=True) == "FULL"
    assert (
        tracker.update(state, now_mono=400, cloud_age=301, policy_valid=True)
        == "LOCAL_CONSERVATIVE"
    )
    assert tracker.update(state, now_mono=401, cloud_age=3601, policy_valid=True) == "SAFE_HOLD"
    assert tracker.update(state, now_mono=402, cloud_age=0, policy_valid=True) == "SAFE_HOLD"
    assert tracker.update(state, now_mono=582, cloud_age=0, policy_valid=True) == "FULL"
