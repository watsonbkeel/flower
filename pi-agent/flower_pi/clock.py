from datetime import datetime, timezone
import subprocess
import time


def ntp_synchronized():
    try:
        result = subprocess.run(
            ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.returncode == 0 and result.stdout.strip() == "yes"
    except (OSError, subprocess.TimeoutExpired):
        return False


class TrustedClock:
    def __init__(self, ntp_probe=ntp_synchronized, max_jump_seconds=5):
        self.ntp_probe = ntp_probe
        self.max_jump_seconds = max_jump_seconds
        self.anchor_wall = time.time()
        self.anchor_mono = time.monotonic()
        self.last_probe = None
        self.last_result = False

    def trusted(self):
        now = time.monotonic()
        if abs((time.time() - self.anchor_wall) - (now - self.anchor_mono)) > self.max_jump_seconds:
            return False
        if self.last_probe is None or now - self.last_probe > 30:
            self.last_result = self.ntp_probe()
            self.last_probe = now
        return self.last_result

    def utcnow(self):
        if not self.trusted():
            raise ValueError("TIME_UNTRUSTED")
        return datetime.now(timezone.utc)

    @staticmethod
    def monotonic():
        return time.monotonic()

    @staticmethod
    def sleep(seconds):
        time.sleep(seconds)
