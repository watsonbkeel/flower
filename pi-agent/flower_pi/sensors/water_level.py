class WaterLevel:
    def __init__(self, low_samples=5, recovery_seconds=10, sample_seconds=0.2):
        self.ok = False
        self.low_samples = low_samples
        self.recovery_seconds = recovery_seconds
        self.sample_seconds = sample_seconds
        self.low_count = 0
        self.good_since = None
        self.last_sample = None

    def update(self, raw_water_ok, monotonic):
        if self.last_sample is not None and monotonic - self.last_sample < self.sample_seconds - 1e-8:
            return self.ok
        self.last_sample = monotonic
        if raw_water_ok is not True:
            self.good_since = None
            self.low_count += 1
            if self.low_count >= self.low_samples:
                self.ok = False
        else:
            self.low_count = 0
            if self.good_since is None:
                self.good_since = monotonic
            if monotonic - self.good_since >= self.recovery_seconds - 1e-8:
                self.ok = True
        return self.ok


class P451:
    def __init__(self, pin=27):
        from gpiozero import DigitalInputDevice
        self.device = DigitalInputDevice(pin, pull_up=True)

    def read(self):
        return bool(self.device.is_active)  # With pull-up, active means grounded LOW.
