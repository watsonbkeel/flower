from dataclasses import dataclass
import math

NONBLOCKING_FAULTS = {"BLE_STALE", "CAMERA_UNAVAILABLE", "CLOUD_OFFLINE", "PROFILE_STALE"}


@dataclass(frozen=True)
class Permission:
    allowed: bool
    reason: str


def safety_reason(state, check_activity=True):
    if check_activity and state.activity != "IDLE":
        return "BUSY"
    if state.water_level_ok is not True:
        return "LOW_WATER"
    if state.soil_pct is None or not math.isfinite(state.soil_pct) or not 0 <= state.soil_pct <= 100:
        return "SOIL_SENSOR_FAULT"
    if not state.time_trusted:
        return "TIME_UNTRUSTED"
    if not state.calibration_valid:
        return "CALIBRATION_MISSING"
    if not state.profile_valid:
        return "PROFILE_MISSING"
    faults = set(state.fault_codes) - NONBLOCKING_FAULTS
    return sorted(faults)[0] if faults else None


def can_dispense(state, source, *, policy_valid=False, local_test=False, test_seconds=0):
    if state.operating_mode in {"SAFE_HOLD", "STARTING"}:
        return Permission(False, state.operating_mode)
    reason = safety_reason(state)
    if reason:
        return Permission(False, reason)
    if source in {"cloud_auto", "user_manual"}:
        allowed = state.operating_mode == "FULL" and "CLOUD_OFFLINE" not in state.fault_codes
    elif source == "local_fallback":
        allowed = state.operating_mode == "LOCAL_CONSERVATIVE" and policy_valid
    elif source == "maintenance_test":
        allowed = local_test and 0 < test_seconds <= 1 and state.operating_mode == "FULL"
    else:
        allowed = False
    return Permission(allowed, "OK" if allowed else "SOURCE_NOT_ALLOWED")
