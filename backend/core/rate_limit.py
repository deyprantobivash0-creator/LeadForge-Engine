"""Bounded process-local login budget. Forwarded headers never choose a key."""
import hashlib
import math
import threading
import time

from fastapi import HTTPException, Request
from backend.core.config import settings


class LoginLimiter:
    def __init__(self, slots=1024, limit=10, seconds=60, clock=time.monotonic,
                 message="Too many login attempts."):
        self.slots, self.limit, self.seconds, self.clock = slots, limit, seconds, clock
        self.message = message
        self._lock = threading.Lock()
        self._buckets = [(0.0, 0)] * slots

    def reset(self):
        with self._lock:
            self._buckets[:] = [(0.0, 0)] * self.slots

    def check(self, request: Request):
        if not settings.RATE_LIMIT_ENABLED:
            return
        peer = request.client.host if request.client else "unknown"
        self.check_key(peer)

    def check_key(self, key: str):
        if not settings.RATE_LIMIT_ENABLED:
            return
        slot = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") % self.slots
        with self._lock:
            now = self.clock()
            expires, count = self._buckets[slot]
            if expires <= now:
                expires, count = now + self.seconds, 0
            if count >= self.limit:
                raise HTTPException(429, self.message,
                                    headers={"Retry-After": str(max(1, math.ceil(expires-now)))})
            self._buckets[slot] = (expires, count + 1)


limiter = LoginLimiter()
password_change_limiter = LoginLimiter(limit=5, seconds=300,
                                      message="Too many password change attempts. Try again in five minutes.")
