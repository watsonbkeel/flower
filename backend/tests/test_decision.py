from datetime import datetime, timedelta, timezone

import pytest

from flower.services.decision import DecisionInput, decide
from flower.services.knowledge import Knowledge, MemoryRule, compile_policy
from flower_pi.policy.fallback import Policy, policy_digest

NOW = datetime(2026, 9, 13, 0, tzinfo=timezone.utc)


def context(**values):
    return DecisionInput(
        **(
            dict(
                now=NOW,
                timezone="Asia/Shanghai",
                soil_pct=30,
                target_min=40,
                target_max=65,
                windows=[("06:00", "09:00"), ("17:00", "20:00")],
                pot_size="medium",
                pot_material="plastic",
                has_drainage=True,
                placement_type="indoor",
                water_level_ok=True,
                time_trusted=True,
                calibration_valid=True,
                profile_confirmed=True,
                operating_mode="FULL",
                activity="IDLE",
                auto_mode=True,
                interval_ok=True,
                quota_remaining_ml=120,
            )
            | values
        )
    )


@pytest.mark.parametrize(
    "values,expected,reason",
    [
        ({"soil_pct": 40}, "hold", "above_threshold"),
        ({"soil_pct": 39}, "water", "within_window_below_target"),
        ({"soil_pct": 30, "now": NOW + timedelta(hours=4)}, "defer", "outside_window"),
        ({"soil_pct": 25, "now": NOW + timedelta(hours=4)}, "water", "urgent_override_window"),
        ({"soil_pct": 26, "now": NOW + timedelta(hours=4)}, "defer", "outside_window"),
        (
            {"soil_pct": 10, "placement_type": "outdoor", "rain_expected": True},
            "defer",
            "rain_expected",
        ),
        ({"soil_pct": 10, "rain_expected": True}, "water", "within_window_below_target"),
    ],
)
def test_complete_ordered_decision_branches(values, expected, reason):
    result = decide(context(**values))
    assert result.decision == expected
    assert result.reason == reason
    assert result == decide(context(**values))


@pytest.mark.parametrize(
    "values",
    [
        {"water_level_ok": False},
        {"soil_pct": None},
        {"time_trusted": False},
        {"calibration_valid": False},
        {"profile_confirmed": False},
        {"operating_mode": "SAFE_HOLD"},
        {"activity": "WATERING"},
        {"auto_mode": False},
        {"interval_ok": False},
        {"quota_remaining_ml": 0},
        {"active_command": True},
    ],
)
def test_hard_gates_hold(values):
    assert decide(context(**values)).decision == "hold"


def test_configuration_modifiers_and_memory_are_bounded():
    baseline = decide(context())
    warm = decide(context(temperature_c=35, air_humidity=25, air_fresh=True))
    stale = decide(context(temperature_c=35, air_humidity=25, air_fresh=False))
    assert warm.effective_min_pct > baseline.effective_min_pct
    assert stale.effective_min_pct <= baseline.effective_min_pct
    no_drain = decide(context(soil_pct=10, has_drainage=False))
    assert no_drain.pulse_ml <= baseline.pulse_ml / 2
    memory = MemoryRule(
        preferred_windows=[["18:00", "21:00"]],
        watering_style="small_portions",
        soil_preference="let_surface_dry",
        threshold_shift_pct=-3,
    )
    result = decide(context(memory_rules=[memory.model_dump()]))
    assert result.decision == "defer"
    assert result.effective_min_pct < baseline.effective_min_pct
    with pytest.raises(ValueError):
        MemoryRule(threshold_shift_pct=100)


@pytest.mark.parametrize("field", ["amount_ml", "pump_seconds", "pulse_ml", "max_pulses", "GPIO"])
def test_llm_execution_fields_are_rejected(field):
    with pytest.raises(ValueError):
        Knowledge(**{field: 10})


def test_policy_compilation_matches_pi_contract_and_timezone():
    policy = compile_policy(
        profile={"soil_target_min_pct": 40, "soil_target_max_pct": 65},
        profile_version=2,
        policy_version=3,
        now=NOW,
        timezone_name="Asia/Shanghai",
        windows=[["06:00", "09:00"]],
        pulse_ml=10,
        max_24h_ml=120,
    )
    parsed = Policy.model_validate(policy["policy"])
    assert parsed.max_24h_ml == 60
    assert parsed.max_pulses == 1
    assert parsed.trigger_soil_below_pct < 40
    assert parsed.valid_until <= NOW + timedelta(days=7)
    assert policy["policy_hash"] == policy_digest(parsed)
