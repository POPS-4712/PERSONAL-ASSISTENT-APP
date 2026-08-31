"""Small sliding-window rate limiter used as a FastAPI dependency.

In-process, which is correct for the single-process uvicorn this stack runs.
Kept as a dependency (not a decorator) so it never interferes with FastAPI's
handler-signature introspection.
"""

import ipaddress
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


def _peer_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_trusted_proxy(ip_str: str) -> bool:
    nets = get_settings().trusted_proxy_networks
    if not nets:
        return False
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(ip in net for net in nets)


def _clientip(request: Request) -> str:
    """Best-effort real client IP for rate-limiting.

    X-Forwarded-For is trivially spoofable, so it is honoured only when the
    immediate peer (``request.client.host``) is a configured trusted proxy. In
    that case we walk the forwarded chain from the right, skipping hops that are
    themselves trusted proxies, and take the first address we did not put there.
    With no trusted proxies configured (desktop / directly-exposed backend) the
    header is ignored entirely and the TCP peer address is used.
    """
    peer = _peer_ip(request)
    if not _is_trusted_proxy(peer):
        return peer

    fwd = request.headers.get("x-forwarded-for")
    if not fwd:
        return peer
    chain = [p.strip() for p in fwd.split(",") if p.strip()]
    for candidate in reversed(chain):
        if not _is_trusted_proxy(candidate):
            return candidate
    return chain[0] if chain else peer


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
