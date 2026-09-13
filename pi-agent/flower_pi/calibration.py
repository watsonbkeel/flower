from datetime import datetime
import statistics

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Calibration(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    flow_ml_sec: float = Field(gt=0, le=30)
    afterdrip_mean_ml: float = Field(ge=0, le=3)
    afterdrip_max_ml: float = Field(ge=0, le=3)
    min_run_sec: float = Field(gt=0, le=10)
    adc_dry: float = Field(ge=0, le=32767)
    adc_wet: float = Field(ge=0, le=32767)
    insert_depth_mark: str = Field(min_length=1)
    calibrated_at: datetime

    @model_validator(mode="after")
    def valid(self):
        if self.afterdrip_mean_ml > self.afterdrip_max_ml:
            raise ValueError("afterdrip mean exceeds maximum")
        if abs(self.adc_dry - self.adc_wet) < 1000:
            raise ValueError("soil calibration span below 1000 ADC counts")
        if self.calibrated_at.tzinfo is None:
            raise ValueError("calibration timestamp must be timezone aware")
        return self

    @property
    def min_controllable_ml(self):
        return self.flow_ml_sec * self.min_run_sec + self.afterdrip_mean_ml

    def run_seconds(self, pulse_ml):
        if pulse_ml < self.min_controllable_ml:
            raise ValueError("BELOW_MINIMUM_DOSE")
        return max(self.min_run_sec, (pulse_ml - self.afterdrip_mean_ml) / self.flow_ml_sec)


def validate_measurements(flow_volumes, afterdrip, min_run_sec, adc_dry, adc_wet, depth, now):
    import math

    if len(flow_volumes) != 3 or len(afterdrip) != 3:
        raise ValueError("three flow and three afterdrip measurements required")
    if any(not math.isfinite(v) or v < 0 for v in flow_volumes + afterdrip):
        raise ValueError("measurements must be finite and nonnegative")
    average = statistics.mean(flow_volumes)
    if average <= 0 or max(flow_volumes) - min(flow_volumes) > average * 0.15:
        raise ValueError("flow range exceeds 15 percent")
    return Calibration(
        flow_ml_sec=average / 10,
        afterdrip_mean_ml=statistics.mean(afterdrip),
        afterdrip_max_ml=max(afterdrip),
        min_run_sec=min_run_sec,
        adc_dry=adc_dry,
        adc_wet=adc_wet,
        insert_depth_mark=depth,
        calibrated_at=now,
    )
