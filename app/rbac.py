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
    
    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.role == UserRole.ADMIN
    
    def is_operator(self) -> bool:
        """Check if user is operator or admin."""
        return self.role in (UserRole.ADMIN, UserRole.OPERATOR)
    
    def is_viewer(self) -> bool:
        """Check if user is viewer (any authenticated user)."""
        return self.role in (UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)
    
    def can_write(self) -> bool:
        """Check if user can write (admin or operator)."""
        return self.role in (UserRole.ADMIN, UserRole.OPERATOR)
    
    def can_read(self) -> bool:
        """Check if user can read (any role)."""
        return True


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
                return JSONResponse(
                    {"error": "Forbidden", "message": f"Required roles: {[r.value for r in roles]}"},
                    status_code=403
                )
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_admin(func: Callable) -> Callable:
    """Decorator requiring ADMIN role."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = get_request_user(request)
        if not user or not user.is_admin():
            return JSONResponse(
                {"error": "Forbidden", "message": "Admin access required"},
                status_code=403
            )
        return await func(request, *args, **kwargs)
    return wrapper


def require_operator(func: Callable) -> Callable:
    """Decorator requiring OPERATOR or ADMIN role."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = get_request_user(request)
        if not user or not user.is_operator():
            return JSONResponse(
                {"error": "Forbidden", "message": "Operator or Admin access required"},
                status_code=403
            )
        return await func(request, *args, **kwargs)
    return wrapper


def require_auth(func: Callable) -> Callable:
    """Decorator requiring any authenticated user."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = get_request_user(request)
        if not user:
            return JSONResponse(
                {"error": "Unauthorized", "message": "Authentication required"},
                status_code=401
            )
        return await func(request, *args, **kwargs)
    return wrapper


# Role groups for convenience
ALL_ROLES = (UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)
WRITE_ROLES = (UserRole.ADMIN, UserRole.OPERATOR)
READ_ROLES = ALL_ROLES

# Permission matrix documentation
PERMISSIONS = {
    UserRole.ADMIN: {
        "description": "Full access to all features",
        "can_create": True,
        "can_read": True,
        "can_update": True,
        "can_delete": True,
        "can_manage_users": True,
        "can_execute": True,
    },
    UserRole.OPERATOR: {
        "description": "Can manage resources and execute tasks",
        "can_create": True,
        "can_read": True,
        "can_update": True,
        "can_delete": True,
        "can_manage_users": False,
        "can_execute": True,
    },
    UserRole.VIEWER: {
        "description": "Read-only access",
        "can_create": False,
        "can_read": True,
        "can_update": False,
        "can_delete": False,
        "can_manage_users": False,
        "can_execute": False,
    },
}
