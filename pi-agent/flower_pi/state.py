from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceState:
    operating_mode: str = "STARTING"
    activity: str = "IDLE"
    fault_codes: tuple[str, ...] = ()
    water_level_ok: bool | None = None
    soil_pct: float | None = None
    time_trusted: bool = False
    calibration_valid: bool = False
    profile_valid: bool = False


class ModeTracker:
    def __init__(self, conservative_after=300, hold_after=3600, recovery_seconds=180):
        self.conservative_after = conservative_after
        self.hold_after = hold_after
        self.recovery_seconds = recovery_seconds
        self.mode = "STARTING"
        self.healthy_since = None

    def update(self, state, *, now_mono, cloud_age, policy_valid):
        from flower_pi.safety.gate import safety_reason

        reason = safety_reason(state, check_activity=False)
        if (
            reason
            or cloud_age >= self.hold_after
            or (cloud_age >= self.conservative_after and not policy_valid)
        ):
            self.mode = "SAFE_HOLD"
            self.healthy_since = None
        elif cloud_age >= self.conservative_after:
            self.mode = "LOCAL_CONSERVATIVE"
            self.healthy_since = None
        elif cloud_age > 90:
            self.mode = "SAFE_HOLD"
            self.healthy_since = None
        else:
            if self.healthy_since is None:
                self.healthy_since = now_mono
            if now_mono - self.healthy_since >= self.recovery_seconds:
                self.mode = "FULL"
        return self.mode
