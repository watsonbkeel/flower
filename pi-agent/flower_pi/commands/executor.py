from dataclasses import replace
from datetime import datetime, timedelta
import threading
from zoneinfo import ZoneInfo
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from flower_pi.safety.gate import can_dispense
from flower_pi.safety.watchdog import Watchdog


class DispenseCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str
    device_id: str
    source: Literal["cloud_auto", "user_manual", "local_fallback", "maintenance_test"]
    run_mode: Literal["real", "demo", "offline_demo"]
    target_ml: float = Field(gt=0, le=60)
    pulse_ml: float = Field(gt=0, le=40)
    max_pulses: int = Field(ge=1, le=3)
    max_continuous_sec: float = Field(gt=0, le=10)
    afterdrip_settle_sec: float = Field(ge=30)
    absorb_wait_sec: float = Field(ge=45)
    session_max_duration_sec: float = Field(gt=0, le=1800)
    claim_deadline_at: datetime
    claimed_at: datetime | None = None
    start_grace_sec: int = Field(default=30, ge=1, le=30)
    stop_soil_pct: float = Field(ge=0, le=100)


class Executor:
    def __init__(
        self,
        device_id,
        pump,
        ledger,
        state,
        calibration,
        clock,
        limit_ml=120,
        interval_hours=6,
        boot_id="unknown",
    ):
        self.device_id, self.pump, self.ledger = device_id, pump, ledger
        self.state, self.calibration, self.clock = state, calibration, clock
        self.limit_ml, self.interval_hours, self.boot_id = limit_ml, interval_hours, boot_id
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.watchdog = Watchdog(pump)
        self.activity = "IDLE"
        self.pump.off()

    def stop(self):
        self.cancel.set()
        self.pump.off()

    def execute(self, command, *, policy=None, on_started=None, on_progress=None):
        if not self.lock.acquire(blocking=False):
            return {"status": "failed", "reason": "BUSY"}
        reserved = False
        actual = 0.0
        pulses = []
        self.cancel.clear()
        try:
            now = self.clock.utcnow()
            if command.device_id != self.device_id or command.claim_deadline_at.tzinfo is None:
                raise ValueError("COMMAND_OWNERSHIP")
            if command.source != "local_fallback" and (
                command.claimed_at is None
                or command.claimed_at.tzinfo is None
                or now >= command.claimed_at + timedelta(seconds=command.start_grace_sec)
                or command.claimed_at > now
            ):
                raise ValueError("START_GRACE_EXPIRED")
            if command.source == "maintenance_test":
                raise ValueError("REMOTE_MAINTENANCE_FORBIDDEN")
            policy_valid = False
            limit, interval = self.limit_ml, self.interval_hours
            if command.source == "local_fallback":
                if policy is None:
                    raise ValueError("POLICY_MISSING")
                policy_valid = policy.permits(
                    now,
                    soil_pct=self.state().soil_pct,
                    last_watered=self.ledger.last_watered(),
                    used_ml=self.ledger.used(now),
                )
                if command.max_pulses != 1 or command.target_ml != policy.pulse_ml:
                    raise ValueError("POLICY_DOSE_MISMATCH")
                limit, interval = (
                    min(limit, policy.max_24h_ml),
                    max(interval, policy.min_interval_hours),
                )
            permission = can_dispense(self.state(), command.source, policy_valid=policy_valid)
            if not permission.allowed:
                raise ValueError(permission.reason)
            if command.run_mode == "real" and command.absorb_wait_sec < 300:
                raise ValueError("ABSORB_WAIT_TOO_SHORT")
            if command.target_ml > command.pulse_ml * command.max_pulses:
                raise ValueError("INVALID_SESSION_VOLUME")
            # Validate every dose, including a possible remainder, before reserving or opening.
            remaining = command.target_ml
            doses = []
            while remaining > 1e-8:
                dose = min(remaining, command.pulse_ml)
                seconds = self.calibration.run_seconds(dose)
                if seconds > command.max_continuous_sec:
                    raise ValueError("CONTINUOUS_LIMIT")
                doses.append((dose, seconds))
                remaining -= dose
            started = self.clock.monotonic()
            self.ledger.reserve(
                command.id,
                command.source,
                command.target_ml,
                now,
                self.boot_id,
                started,
                limit_ml=limit,
                interval_hours=interval,
            )
            reserved = True
            self.activity = "WATERING"
            if on_started:
                on_started()
            deadline = started + command.session_max_duration_sec

            def check():
                if self.cancel.is_set():
                    raise ValueError("CANCELLED")
                if self.clock.monotonic() >= deadline:
                    raise TimeoutError("SESSION_TIMEOUT")
                state = replace(self.state(), activity="IDLE")
                live_policy = policy_valid
                if command.source == "local_fallback":
                    current_time = self.clock.utcnow()
                    local_time = current_time.astimezone(ZoneInfo(policy.timezone)).strftime(
                        "%H:%M"
                    )
                    live_policy = policy.generated_at <= current_time < policy.valid_until and any(
                        start <= local_time < end for start, end in policy.allowed_windows_local
                    )
                permitted = can_dispense(state, command.source, policy_valid=live_policy)
                if not permitted.allowed:
                    raise ValueError(permitted.reason)
                if self.watchdog.tripped.is_set():
                    raise ValueError("WATCHDOG_TRIPPED")

            def wait(seconds):
                end = self.clock.monotonic() + seconds
                while self.clock.monotonic() < end - 1e-8:
                    check()
                    self.clock.sleep(min(0.05, end - self.clock.monotonic()))
                check()

            for dose, seconds in doses:
                check()
                if self.state().soil_pct >= command.stop_soil_pct:
                    break
                self.watchdog.arm(
                    min(command.max_continuous_sec, deadline - self.clock.monotonic())
                )
                try:
                    self.pump._energize()
                    wait(seconds)
                finally:
                    self.watchdog.disarm()
                actual += dose
                self.ledger.progress(command.id, actual)
                pulses.append(
                    {
                        "pulse": len(pulses) + 1,
                        "estimated_ml": dose,
                        "finished_at": self.clock.utcnow().isoformat(),
                    }
                )
                if on_progress:
                    on_progress(pulses)
                wait(command.afterdrip_settle_sec + command.absorb_wait_sec)
            receipt = {
                "status": "succeeded",
                "actual_ml": actual,
                "pulses": pulses,
                "finished_at": self.clock.utcnow().isoformat(),
            }
            self.ledger.set_value("receipt:" + command.id, receipt)
            self.ledger.finish(
                command.id,
                actual_ml=actual,
                now=self.clock.utcnow(),
                monotonic=self.clock.monotonic(),
                verified=True,
            )
            return receipt
        except Exception as exc:
            if reserved:
                self.ledger.provisional(command.id)
            return {
                "status": "timed_out" if isinstance(exc, TimeoutError) else "failed",
                "reason": str(exc)
                if isinstance(exc, (ValueError, TimeoutError))
                else "EXECUTION_FAULT",
                "actual_ml": actual,
                "pulses": pulses,
                "provisional": reserved,
            }
        finally:
            self.watchdog.disarm()
            self.activity = "IDLE"
            self.lock.release()
