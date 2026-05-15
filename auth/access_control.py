from fastapi import Depends, HTTPException, status

from auth.auth_deps import get_current_user
from backend.models.auth_models import UserRole

ROLE_LEVELS = {
    UserRole.CUSTOMER.value: 10,
    UserRole.ADMIN.value: 50,
    UserRole.SUPER_ADMIN.value: 100,
}


def require_role(required_role: UserRole | str):
    normalized_required_role = required_role
    if isinstance(required_role, str):
        normalized = required_role.strip().lower()
        if normalized == "user":
            normalized = UserRole.CUSTOMER.value
        try:
            normalized_required_role = UserRole(normalized)
        except ValueError as exc:
            raise ValueError(f"Unknown role '{required_role}' passed to require_role") from exc

    async def role_dependency(current_user: dict = Depends(get_current_user)) -> dict:
        current_role = str(current_user.get("role", "")).strip().lower()
        current_level = ROLE_LEVELS.get(current_role, 0)
        required_level = ROLE_LEVELS.get(normalized_required_role.value, 0)

        if current_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_dependency
