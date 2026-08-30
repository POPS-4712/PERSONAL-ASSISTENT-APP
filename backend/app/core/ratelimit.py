"""Small sliding-window rate limiter used as a FastAPI dependency.

In-process, which is correct for the single-process uvicorn this stack runs.
Kept as a dependency (not a decorator) so it never interferes with FastAPI's
handler-signature introspection.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import get_settings

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)

# Flipped off under the test environment; a test can force it on.
_enabled = get_settings().environment != "testing"


def set_enabled(value: bool) -> None:
    global _enabled
    _enabled = value


def _clientip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimit:
    def __init__(self, limit: int, window_seconds: int, scope: str):
        self.limit = limit
        self.window = window_seconds
        self.scope = scope

    def __call__(self, request: Request) -> None:
        if not _enabled:
            return
        key = f"{self.scope}:{_clientip(request)}"
        now = time.monotonic()
        with _lock:
            bucket = _hits[key]
            cutoff = now - self.window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                retry = int(bucket[0] + self.window - now) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="rate limit exceeded",
                    headers={"Retry-After": str(retry)},
                )
            bucket.append(now)


_UNIT_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


def from_spec(spec: str, scope: str) -> RateLimit:
    """`from_spec("10/minute", "auth")` -> RateLimit(10, 60, "auth")."""
    count, _, unit = spec.partition("/")
    return RateLimit(int(count), _UNIT_SECONDS[unit.strip().rstrip("s")], scope)


_settings = get_settings()
auth_rate_limit = from_spec(_settings.rate_limit_auth, "auth")
