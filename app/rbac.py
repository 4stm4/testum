# SPDX-License-Identifier: MIT
"""Role-based access control helpers."""
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Iterable, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.models import UserRole


@dataclass
class UserContext:
    """Lightweight representation of the authenticated user."""

    id: Optional[str]
    username: str
    role: UserRole

    def has_any_role(self, roles: Iterable[UserRole]) -> bool:
        """Return True when user has one of the required roles."""

        if self.role == UserRole.ADMIN:
            return True
        return any(self.role == role for role in roles)


def get_request_user(request: Request) -> Optional[UserContext]:
    """Return UserContext stored on request state, if any."""

    return getattr(request.state, "user", None)


def require_roles(*roles: UserRole) -> Callable:
    """Decorator ensuring the authenticated user has one of the given roles."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = get_request_user(request)
            if not user or not user.has_any_role(roles):
                return JSONResponse({"error": "Forbidden"}, status_code=403)
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


ALL_ROLES = (UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)
