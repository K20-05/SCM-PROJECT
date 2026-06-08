import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from auth.rate_limit import clear_rate_limit_state, rate_limit_dependency


class _FakeHeaders(dict):
    def get(self, key, default=None):
        return super().get(key.lower(), default)


def _request(host: str = "127.0.0.1", forwarded_for: str | None = None):
    headers = _FakeHeaders()
    if forwarded_for:
        headers["x-forwarded-for"] = forwarded_for
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    clear_rate_limit_state()
    yield
    clear_rate_limit_state()


def test_rate_limit_blocks_after_configured_attempts():
    dependency = rate_limit_dependency(2, 60, "test-login")
    request = _request()

    asyncio.run(dependency(request))
    asyncio.run(dependency(request))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dependency(request))

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert exc_info.value.detail == "Too many attempts. Please try again later."


def test_rate_limit_uses_forwarded_ip_when_present():
    dependency = rate_limit_dependency(1, 60, "test-forwarded")
    asyncio.run(dependency(_request(host="127.0.0.1", forwarded_for="10.0.0.5, 10.0.0.6")))

    with pytest.raises(HTTPException):
        asyncio.run(dependency(_request(host="127.0.0.2", forwarded_for="10.0.0.5")))

    asyncio.run(dependency(_request(host="127.0.0.1", forwarded_for="10.0.0.7")))
