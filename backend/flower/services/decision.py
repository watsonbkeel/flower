from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
from zoneinfo import ZoneInfo

from flower.services.knowledge import MemoryRule


@dataclass(frozen=True)
class DecisionConfig:
    urgent_gap_pct: float = 15
    hot_c: float = 30
    hot_shift: float = 3
    cold_c: float = 15
    cold_shift: float = -5
    dry_air_pct: float = 35
    dry_air_shift: float = 2
    humid_air_pct: float = 80
    humid_air_shift: float = -2
    small_pot_shift: float = 2
    terracotta_shift: float = 2
    no_drain_shift: float = -10
    memory_shift_limit: float = 5
    pulse_small: float = 10
    pulse_medium: float = 20
    pulse_large: float = 30
    session_max_ml: float = 60
    max_pulses: int = 3


@dataclass(frozen=True)
class DecisionInput:
    now: datetime
    timezone: str
    soil_pct: float | None
    target_min: float
    target_max: float
    windows: list
    pot_size: str
    pot_material: str
    has_drainage: bool
    placement_type: str
    water_level_ok: bool
    time_trusted: bool
    calibration_valid: bool
    profile_confirmed: bool
    operating_mode: str
    activity: str
    auto_mode: bool
    interval_ok: bool
    quota_remaining_ml: float
    active_command: bool = False
    rain_expected: bool = False
    temperature_c: float | None = None
    air_humidity: float | None = None
    air_fresh: bool = False
    memory_rules: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Decision:
    decision: str
    reason: str
    effective_min_pct: float
    effective_max_pct: float
    pulse_ml: float = 0
    max_pulses: int = 0
    session_max_ml: float = 0
    next_window_at: str | None = None
    explain_zh: str = ""


def decide(data: DecisionInput, config=DecisionConfig()):
    threshold = data.target_min
    if data.air_fresh:
        if data.temperature_c is not None:
            if data.temperature_c >= config.hot_c:
                threshold += config.hot_shift
            elif data.temperature_c <= config.cold_c:
                threshold += config.cold_shift
        if data.air_humidity is not None:
            if data.air_humidity < config.dry_air_pct:
                threshold += config.dry_air_shift
            elif data.air_humidity > config.humid_air_pct:
                threshold += config.humid_air_shift
    if data.pot_size == "small":
        threshold += config.small_pot_shift
    if data.pot_material == "terracotta":
        threshold += config.terracotta_shift
    if not data.has_drainage:
        threshold += config.no_drain_shift
    windows = data.windows
    style = "normal"
    shift = 0
    for raw in data.memory_rules:
        rule = MemoryRule.model_validate(raw)
        shift += rule.threshold_shift_pct
        if rule.preferred_windows:
            windows = rule.preferred_windows
        if rule.watering_style != "normal":
            style = rule.watering_style
    threshold = max(
        10,
        min(70, threshold + max(-config.memory_shift_limit, min(config.memory_shift_limit, shift))),
    )
    maximum = max(threshold + 5, data.target_max)

    def result(action, reason, **kwargs):
        explain = {
            "hold": "当前暂不补水",
            "water": "土壤低于触发线，将分次少量补水并复测",
            "defer": "补水已延后",
        }[action]
        return Decision(
            action, reason, threshold, maximum, explain_zh=f"{explain}：{reason}", **kwargs
        )

    gates = [
        (not data.water_level_ok, "LOW_WATER"),
        (data.soil_pct is None or not math.isfinite(data.soil_pct), "SOIL_SENSOR_FAULT"),
        (not data.time_trusted or data.now.tzinfo is None, "TIME_UNTRUSTED"),
        (not data.calibration_valid, "CALIBRATION_MISSING"),
        (not data.profile_confirmed, "PROFILE_MISSING"),
        (data.operating_mode != "FULL", "SAFE_HOLD"),
        (data.activity != "IDLE", "PUMP_BUSY"),
        (not data.auto_mode, "AUTO_MODE_DISABLED"),
        (not data.interval_ok, "MIN_INTERVAL"),
        (data.quota_remaining_ml <= 0, "QUOTA_EXCEEDED"),
        (data.active_command, "ACTIVE_COMMAND"),
    ]
    for blocked, reason in gates:
        if blocked:
            return result("hold", reason)
    try:
        local = data.now.astimezone(ZoneInfo(data.timezone))
    except (KeyError, ValueError):
        return result("hold", "TIMEZONE_INVALID")
    if data.soil_pct >= threshold:
        return result("hold", "above_threshold")
    if data.placement_type != "indoor" and data.rain_expected:
        return result("defer", "rain_expected")
    within = any(start <= local.strftime("%H:%M") < end for start, end in windows)
    if not within and data.soil_pct > threshold - config.urgent_gap_pct:
        candidates = []
        for day in (0, 1):
            for start, _ in windows:
                hour, minute = map(int, start.split(":"))
                candidate = (local + timedelta(days=day)).replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                if candidate > local:
                    candidates.append(candidate)
        return result(
            "defer",
            "outside_window",
            next_window_at=min(candidates).isoformat() if candidates else None,
        )
    normal = {
        "small": config.pulse_small,
        "medium": config.pulse_medium,
        "large": config.pulse_large,
    }
    bounds = {"small": (5, 15), "medium": (10, 30), "large": (15, 40)}
    pulse = normal[data.pot_size]
    if style == "small_portions":
        pulse = bounds[data.pot_size][0]
    elif style == "thorough":
        pulse = bounds[data.pot_size][1]
    session_limit = config.session_max_ml
    if not data.has_drainage:
        pulse /= 2
        session_limit /= 2
    count = min(config.max_pulses, math.floor(min(session_limit, data.quota_remaining_ml) / pulse))
    if count < 1:
        return result("hold", "QUOTA_EXCEEDED")
    return result(
        "water",
        "within_window_below_target" if within else "urgent_override_window",
        pulse_ml=pulse,
        max_pulses=count,
        session_max_ml=pulse * count,
    )
