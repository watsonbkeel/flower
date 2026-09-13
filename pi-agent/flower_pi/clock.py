from datetime import datetime, timezone
import subprocess
import threading
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
    def __init__(
        self,
        ntp_probe=ntp_synchronized,
        max_jump_seconds=5,
        *,
        wall_time=time.time,
        monotonic_time=time.monotonic,
    ):
        self.ntp_probe = ntp_probe
        self.max_jump_seconds = max_jump_seconds
        self.wall_time = wall_time
        self.monotonic_time = monotonic_time
        self.anchor_wall = wall_time()
        self.anchor_mono = monotonic_time()
        self.last_probe = None
        self.last_result = False
        self.stable_since = None
        self.lock = threading.RLock()

    def _sample(self):
        now, wall = self.monotonic_time(), self.wall_time()
        if abs((wall - self.anchor_wall) - (now - self.anchor_mono)) > self.max_jump_seconds:
            self.anchor_wall, self.anchor_mono = wall, now
            self.stable_since = now
            self.last_probe = None
            self.last_result = False
        return now, wall

    def trusted(self):
        with self.lock:
            now, _ = self._sample()
            if self.stable_since is not None and now - self.stable_since < 30:
                return False
            if self.last_probe is None or now - self.last_probe >= 30:
                self.last_result = self.ntp_probe()
                self.last_probe = now
                # A clock correction during the blocking probe invalidates its result.
                self._sample()
            return self.last_result

    def utcnow(self):
        with self.lock:
            if not self.trusted():
                raise ValueError("TIME_UNTRUSTED")
            _, wall = self._sample()
            if not self.last_result:
                raise ValueError("TIME_UNTRUSTED")
            return datetime.fromtimestamp(wall, timezone.utc)

    def monotonic(self):
        return self.monotonic_time()

    @staticmethod
    def sleep(seconds):
        time.sleep(seconds)
