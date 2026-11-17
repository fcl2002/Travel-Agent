"""Bounded per-process login and registration throttling, keyed by the connecting client IP."""

from collections import deque
from math import ceil
from threading import Lock
from time import monotonic

from app.core.exceptions import AuthRateLimitError


class AuthRateLimiter:
    def __init__(self, limit: int = 10, window_seconds: int = 60, max_clients: int = 10000):
        if min(limit, window_seconds, max_clients) < 1:
            raise ValueError("Rate limit parameters must be positive")
        self.limit, self.window_seconds, self.max_clients = limit, window_seconds, max_clients
        self._attempts: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, client: str) -> None:
        now = monotonic()
        with self._lock:
            for key in list(self._attempts):
                if self._attempts[key][-1] <= now - self.window_seconds:
                    del self._attempts[key]
            if client not in self._attempts:
                if len(self._attempts) >= self.max_clients:
                    raise AuthRateLimitError(self.window_seconds)
                self._attempts[client] = deque()
            attempts = self._attempts[client]
            while attempts and attempts[0] <= now - self.window_seconds:
                attempts.popleft()
            if len(attempts) >= self.limit:
                raise AuthRateLimitError(max(1, ceil(attempts[0] + self.window_seconds - now)))
            attempts.append(now)
