# SPDX-License-Identifier: MIT
"""Simple in-memory rate limiting middleware."""
import asyncio
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Limit the number of requests per client within a sliding window."""

    def __init__(self, app, limit: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        client_host = request.client.host if request.client else "unknown"
        key = f"{client_host}:{request.url.path}"
        now = time.monotonic()

        async with self._lock:
            records = self._requests[key]

            # Remove expired entries
            while records and now - records[0] > self.window_seconds:
                records.popleft()

            if len(records) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - records[0])))
                return JSONResponse(
                    {
                        "error": "Too many requests",
                        "retry_after": retry_after,
                    },
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )

            records.append(now)

        response = await call_next(request)
        response.headers.setdefault("X-RateLimit-Limit", str(self.limit))
        response.headers.setdefault("X-RateLimit-Remaining", str(self.limit - len(self._requests[key])))
        response.headers.setdefault("X-RateLimit-Window", str(self.window_seconds))
        return response
