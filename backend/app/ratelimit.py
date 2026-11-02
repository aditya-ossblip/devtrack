"""Limit how often one address can hit the sign-in routes.

Without this, a script can try thousands of passwords a minute against the
login form, or create accounts in a loop. Ten tries in ten minutes is far more
than a person who mistyped needs, and far too few for anyone guessing.

The counts live in memory, per app. That is exactly right for one server
process, which is what the free Render plan runs. If DevTrack ever runs on
several processes, the counts would need a shared store (Redis) instead.
"""

import math
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import current_app, request

from .errors import ApiError

_EXTENSION_KEY = 'devtrack_rate_limits'


class RateLimiter:
    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()
        self._calls = 0

    def hit(self, key: str, limit: int, window: float, now: float | None = None) -> float:
        """Record one attempt. Returns 0 if allowed, else seconds until the next is."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= limit:
                return hits[0] + window - now
            hits.append(now)

            # Now and then, drop addresses that have gone quiet, so the table
            # does not grow with every visitor the server has ever seen.
            self._calls += 1
            if self._calls % 1000 == 0:
                for stale in [k for k, v in self._hits.items() if not v or v[-1] <= now - window]:
                    del self._hits[stale]
            return 0.0


def _limiter(app) -> RateLimiter:
    limiter = app.extensions.get(_EXTENSION_KEY)
    if limiter is None:
        limiter = app.extensions[_EXTENSION_KEY] = RateLimiter()
    return limiter


def limited(bucket: str):
    """Decorator: at most AUTH_RATE_LIMIT_COUNT calls per address per window."""

    def decorate(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            app = current_app._get_current_object()
            limit = app.config.get('AUTH_RATE_LIMIT_COUNT', 10)
            window = app.config.get('AUTH_RATE_LIMIT_WINDOW', 600)
            # request.remote_addr is the visitor's address: on Render it comes
            # from X-Forwarded-For through ProxyFix (see create_app).
            key = f'{bucket}:{request.remote_addr or "unknown"}'
            wait = _limiter(app).hit(key, limit, window)
            if wait:
                minutes = max(1, math.ceil(wait / 60))
                raise ApiError(
                    f'Too many attempts. Wait {minutes} minute{"s" if minutes != 1 else ""} and try again.',
                    429,
                )
            return view(*args, **kwargs)

        return wrapper

    return decorate
