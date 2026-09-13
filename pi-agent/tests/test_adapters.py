import ast
from pathlib import Path

from flower_pi.actuators.pump import MockPump
from flower_pi.safety.watchdog import Watchdog
from flower_pi.clock import TrustedClock
from flower_pi.sensors.air import AirReading, AirProviderSelector
from test_safety import NOW


def test_independent_watchdog_closes_while_executor_is_blocked():
    pump = MockPump()
    watchdog = Watchdog(pump)
    watchdog.arm(0.03)
    pump._energize()
    assert watchdog.tripped.wait(timeout=1)
    assert not pump.commanded_on
    watchdog.disarm()


def test_clock_requires_ntp_and_detects_wall_jumps():
    clock = TrustedClock(ntp_probe=lambda: False)
    assert not clock.trusted()
    clock = TrustedClock(ntp_probe=lambda: True)
    assert clock.trusted()
    clock.anchor_wall -= 100
    assert not clock.trusted()


def test_air_fallback_and_staleness():
    class Provider:
        def read(self):
            return AirReading(status="BINDKEY_REQUIRED")

    class Wired:
        def read(self):
            return AirReading(
                status="READY", temperature_c=23, humidity_pct=50, observed_at=NOW, provider="sht30"
            )

    selector = AirProviderSelector(Provider(), Wired())
    assert selector.read(NOW).provider == "sht30"
    assert selector.read(NOW).status == "READY"


def test_optional_sensor_failure_is_contained():
    class Broken:
        def read(self):
            raise OSError("injected BLE fault")

    assert AirProviderSelector(Broken()).read(NOW).status == "STALE"


def test_no_voice_or_http_entry_can_energize():
    root = Path("pi-agent/flower_pi")
    callers = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "_energize":
                    callers.append(str(path.relative_to(root)))
        assert "aibot" not in path.read_text()
        assert "HTTPServer" not in path.read_text()
    assert set(callers) == {"commands/executor.py"}


def test_real_telemetry_omits_mock_air_values():
    from flower_pi.main import air_telemetry
    from flower_pi.sensors.air import MockAir

    values = air_telemetry(MockAir().read(), "real")
    assert values["temperature_c"] is None
    assert values["air_humidity"] is None
    assert values["sensor_health"]["air_source_type"] == "mock"
