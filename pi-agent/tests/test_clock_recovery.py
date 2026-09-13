from datetime import datetime, timezone

import pytest

from flower_pi.clock import TrustedClock
from flower_pi.state import DeviceState, ModeTracker


class TimeSource:
    def __init__(self):
        self.wall = 1_789_257_600.0
        self.mono = 0.0
        self.synced = True
        self.probes = 0

    def advance(self, seconds):
        self.wall += seconds
        self.mono += seconds

    def probe(self):
        self.probes += 1
        return self.synced

    def clock(self):
        return TrustedClock(
            self.probe, wall_time=lambda: self.wall, monotonic_time=lambda: self.mono
        )


@pytest.mark.parametrize("jump", [3600, -3600])
def test_time_jump_latches_untrusted_then_revalidates_without_restart(jump):
    source = TimeSource()
    clock = source.clock()
    assert clock.trusted()
    source.wall += jump
    assert not clock.trusted()
    for _ in range(10):
        assert not clock.trusted()
    with pytest.raises(ValueError, match="TIME_UNTRUSTED"):
        clock.utcnow()
    source.advance(29)
    assert not clock.trusted()
    source.advance(1)
    assert clock.trusted()
    assert source.probes == 2
    assert clock.utcnow() == datetime.fromtimestamp(source.wall, timezone.utc)


def test_repeated_jump_restarts_stability_and_ntp_failure_stays_closed():
    source = TimeSource()
    clock = source.clock()
    assert clock.trusted()
    source.wall += 100
    assert not clock.trusted()
    source.advance(29)
    source.wall -= 200
    assert not clock.trusted()
    source.advance(1)
    assert not clock.trusted()
    source.synced = False
    source.advance(29)
    assert not clock.trusted()
    source.synced = True
    source.advance(30)
    assert clock.trusted()


def test_jump_during_ntp_probe_cannot_be_reported_trusted():
    source = TimeSource()

    def changing_probe():
        source.wall += 3600
        return True

    clock = TrustedClock(
        changing_probe, wall_time=lambda: source.wall, monotonic_time=lambda: source.mono
    )
    assert not clock.trusted()


def test_time_recovery_does_not_bypass_mode_recovery_window():
    source = TimeSource()
    clock = source.clock()
    tracker = ModeTracker()

    def mode():
        return tracker.update(
            DeviceState(
                water_level_ok=True,
                soil_pct=20,
                time_trusted=clock.trusted(),
                calibration_valid=True,
                profile_valid=True,
            ),
            now_mono=source.mono,
            cloud_age=0,
            policy_valid=True,
        )

    assert mode() == "STARTING"
    source.advance(180)
    assert mode() == "FULL"
    source.wall += 3600
    assert mode() == "SAFE_HOLD"
    source.advance(30)
    assert mode() == "SAFE_HOLD"
    source.advance(179)
    assert mode() == "SAFE_HOLD"
    source.advance(1)
    assert mode() == "FULL"
