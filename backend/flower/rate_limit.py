from collections import OrderedDict, deque
import threading
import time

from flower.errors import DomainError


class RateLimiter:
    def __init__(self, capacity=10000):
        self.buckets = OrderedDict()
        self.lock = threading.Lock()
        self.capacity = capacity

    def check(self, key, limit=6, seconds=60):
        now = time.monotonic()
        with self.lock:
            bucket = self.buckets.setdefault(key, deque())
            self.buckets.move_to_end(key)
            while bucket and bucket[0] <= now - seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                raise DomainError(
                    "RATE_LIMITED", "操作过于频繁，请稍后重试", status=429, retryable=True
                )
            bucket.append(now)
            while len(self.buckets) > self.capacity:
                self.buckets.popitem(last=False)
