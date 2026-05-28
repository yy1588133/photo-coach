"""
Simple in-memory sliding-window rate limiter.
No external dependencies — suitable for single-process deployments (MVP).
"""
import time
from collections import defaultdict


class RateLimiter:
    """Per-IP sliding-window rate limiter."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        window = self._windows[key]
        # in-place trim — keeps the list from growing unbounded
        while window and window[0] < cutoff:
            window.pop(0)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        self._prune(key, now)
        if len(self._windows[key]) >= self.max_requests:
            return False
        self._windows[key].append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        self._prune(key, now)
        return max(0, self.max_requests - len(self._windows[key]))


# Shared singleton
limiter = RateLimiter(max_requests=60, window_seconds=60)


def get_client_ip(request) -> str:
    """Extract best-effort client IP from request headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "unknown"


async def rate_limit_middleware(request, call_next):
    """ASGI middleware that rate-limits by client IP."""
    client_ip = get_client_ip(request)
    if not limiter.is_allowed(client_ip):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=429,
            content={
                "detail": "请求过于频繁，请稍后再试。",
                "retry_after_seconds": limiter.window_seconds,
            },
            headers={"Retry-After": str(limiter.window_seconds)},
        )
    return await call_next(request)
