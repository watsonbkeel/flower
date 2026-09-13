from collections import deque
import math
import statistics


class SoilFilter:
    def __init__(self, dry, wet, minimum_span=1000):
        if not math.isfinite(dry) or not math.isfinite(wet) or abs(dry - wet) < minimum_span:
            raise ValueError("soil calibration missing")
        self.dry, self.wet = dry, wet
        self.samples = deque(maxlen=5)
        self.invalid_count = 0
        self.fault = True
        self.value = None

    def update(self, raw):
        valid = raw is not None and math.isfinite(raw) and 0 < raw < 32767
        self.samples.append(raw if valid else None)
        self.invalid_count = 0 if valid else self.invalid_count + 1
        values = [v for v in self.samples if v is not None]
        if self.invalid_count >= 5 or len(values) < 3:
            self.value = None
            self.fault = True
        else:
            median = statistics.median(values)
            self.value = max(0, min(100, (self.dry - median) / (self.dry - self.wet) * 100))
            self.fault = False
        return self.value


class ADS1115:
    def __init__(self, channel=0):
        import board
        import busio
        import adafruit_ads1x15.ads1115 as ADS
        from adafruit_ads1x15.analog_in import AnalogIn

        self.device = ADS.ADS1115(busio.I2C(board.SCL, board.SDA), address=0x48, gain=1)
        self.input = AnalogIn(self.device, channel)

    def read(self):
        return self.input.value
