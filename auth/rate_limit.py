from collections import defaultdict, deque
from time import monotonic
from typing import Deque

from fastapi import HTTPException, Request, status

from backend.config.app_config import settings


_attempts: dict[str, Deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def rate_limit_dependency(limit: int, window_seconds: int, scope: str):
    async def dependency(request: Request) -> None:
        now = monotonic()
        key = f"{scope}:{client_ip(request)}"
        attempts = _attempts[key]

        while attempts and now - attempts[0] >= window_seconds:
            attempts.popleft()

        if len(attempts) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please try again later.",
            )

        attempts.append(now)

    return dependency


auth_rate_limit = rate_limit_dependency(
    settings.auth_rate_limit_requests,
    settings.auth_rate_limit_window_seconds,
    "auth",
)


def clear_rate_limit_state() -> None:
    _attempts.clear()
