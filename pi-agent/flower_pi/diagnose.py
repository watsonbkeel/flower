import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
import threading

from flower_pi.calibration import Calibration
from flower_pi.clock import TrustedClock
from flower_pi.config import PiSettings
from flower_pi.storage.ledger import Ledger


def main():
    parser = argparse.ArgumentParser(description="只读设备诊断；不会开泵")
    parser.add_argument("--pump-test", action="store_true")
    parser.add_argument("--ble-probe", action="store_true")
    args = parser.parse_args()
    if args.pump_test:
        raise SystemExit("B08：真实标定/诊断授权规则待明确，泵保持关闭。")
    settings = PiSettings()
    clock = TrustedClock()
    data = {
        "spec_version": "2.2.2",
        "hardware_mode": settings.hardware_mode,
        "time_trusted": clock.trusted(),
        "pump_test": "NOT_RUN",
    }
    try:
        calibration = Calibration.model_validate_json(settings.calibration_path.read_text())
        data["calibration"] = calibration.model_dump(mode="json")
        data["min_controllable_ml"] = calibration.min_controllable_ml
    except (OSError, ValueError):
        data["calibration"] = "MISSING"
    if settings.local_db_path.exists():
        ledger = Ledger(settings.local_db_path)
        data["used_24h_ml"] = ledger.used(clock.utcnow()) if clock.trusted() else "TIME_UNTRUSTED"
        data["fallback_policy"] = ledger.value("fallback")
        data["pending_uploads"] = len(ledger.pending())
        ledger.close()
    if settings.hardware_mode == "real":
        from flower_pi.sensors.soil import ADS1115
        from flower_pi.sensors.water_level import P451

        for name, factory in [("soil_raw", ADS1115), ("water_level_ok", P451)]:
            try:
                data[name] = factory().read()
            except Exception:
                data[name] = "UNAVAILABLE"
    if args.ble_probe:
        from flower_pi.sensors.air import XiaomiBLE

        ble = XiaomiBLE(settings.xiaomi_device_mac, settings.xiaomi_bindkey)
        stop = threading.Event()

        async def probe():
            task = asyncio.create_task(ble.scan(stop))
            await asyncio.sleep(15)
            stop.set()
            await task

        asyncio.run(probe())
        data["ble"] = asdict(ble.read())
    data["observed_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
