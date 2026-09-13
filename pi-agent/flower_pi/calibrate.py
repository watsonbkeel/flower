"""Import measured values; this tool never energizes the pump."""

import argparse
import json
from pathlib import Path

from flower_pi.calibration import validate_measurements
from flower_pi.clock import TrustedClock


def main():
    parser = argparse.ArgumentParser(description="导入实测标定数据；不执行开泵")
    parser.add_argument("--measurements", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--soil", action="store_true")
    parser.add_argument("--pump", action="store_true")
    parser.add_argument("--afterdrip", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.measurements.read_text())
    if data.get("source_type") != "real":
        raise ValueError("真实标定只接受 real 测量记录")
    calibration = validate_measurements(
        data["flow_volumes_10sec_ml"],
        data["afterdrip_10min_ml"],
        data["min_run_sec"],
        data["adc_dry"],
        data["adc_wet"],
        data["insert_depth_mark"],
        TrustedClock().utcnow(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(calibration.model_dump_json(indent=2))
    temporary.replace(args.output)
    print("标定数据校验通过。自动守护仍需云端确认及完整物理验收。")


if __name__ == "__main__":
    main()
