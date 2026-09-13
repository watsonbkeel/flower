from datetime import datetime, timezone
import threading


def test_telemetry_runs_while_execution_thread_is_blocked(tmp_path):
    from flower_pi.telemetry import TelemetryReporter
    from flower_pi.config import PiSettings

    samples = []
    sent = threading.Event()
    stop = threading.Event()

    class Client:
        def __init__(self, settings):
            pass

        def request(self, method, path, json):
            samples.append(json)
            if len(samples) >= 2:
                sent.set()

        def close(self):
            pass

    settings = PiSettings(local_db_path=tmp_path / "ledger.db", telemetry_interval_sec=1)
    reporter = TelemetryReporter(
        settings,
        stop,
        lambda: {"occurred_at": datetime.now(timezone.utc).isoformat(), "activity": "WATERING"},
        lambda: None,
        client_factory=Client,
    )
    reporter.start()
    try:
        assert sent.wait(3)
        assert all(sample["activity"] == "WATERING" for sample in samples)
    finally:
        stop.set()
        reporter.join(3)
