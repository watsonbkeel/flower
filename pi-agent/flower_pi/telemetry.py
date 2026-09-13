"""Independent telemetry delivery with thread-owned SQLite and HTTP connections."""

from datetime import datetime, timezone
import threading
from uuid import uuid4

from flower_pi.cloud.client import CloudClient
from flower_pi.storage.ledger import Ledger


class TelemetryReporter(threading.Thread):
    def __init__(self, settings, stop, sample, connected, client_factory=CloudClient):
        super().__init__(daemon=True)
        self.settings, self.stop_event = settings, stop
        self.sample, self.connected, self.client_factory = sample, connected, client_factory

    def run(self):
        ledger = Ledger(self.settings.local_db_path)
        client = self.client_factory(self.settings)
        try:
            while not self.stop_event.is_set():
                try:
                    payload = self.sample()
                    key = str(uuid4())
                    payload["event_id"] = key
                    now = datetime.now(timezone.utc)
                    payload["used_24h_ml"] = (
                        ledger.used(now) if payload.get("time_trusted") else 120
                    )
                    ledger.enqueue(key, "/telemetry", payload, now)
                    client.request("POST", "/telemetry", json=payload)
                    ledger.acknowledge(key)
                    self.connected()
                except Exception:
                    pass
                self.stop_event.wait(self.settings.telemetry_interval_sec)
        finally:
            client.close()
            ledger.close()
