import asyncio

import pytest
from fastapi import HTTPException, status

from auth.access_control import require_role
from backend.models.auth_models import UserRole


def test_require_role_blocks_customer_from_admin_endpoints():
    dependency = require_role("admin")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dependency({"role": UserRole.CUSTOMER.value}))

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Insufficient permissions"


def test_require_role_allows_admin_access():
    dependency = require_role("admin")

    result = asyncio.run(dependency({"role": UserRole.ADMIN.value, "email": "admin@example.com"}))

    assert result["role"] == UserRole.ADMIN.value
