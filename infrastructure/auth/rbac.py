# SPDX-License-Identifier: MIT
"""RBAC context and route decorators."""
from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Callable, Iterable, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse

from core.domain.enums import UserRole


@dataclass
class UserContext:
    id: Optional[str]
    username: str
    role: UserRole

    def has_any_role(self, roles: Iterable[UserRole]) -> bool:
        if self.role == UserRole.ADMIN:
            return True
        return any(self.role == r for r in roles)

    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def is_operator(self) -> bool:
        return self.role in (UserRole.ADMIN, UserRole.OPERATOR)

    def can_write(self) -> bool:
        return self.role in (UserRole.ADMIN, UserRole.OPERATOR)


def get_request_user(request: Request) -> Optional[UserContext]:
    return getattr(request.state, "user", None)


def require_admin(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = get_request_user(request)
        if not user or not user.is_admin():
            return JSONResponse({"error": "Admin access required"}, status_code=403)
        return await func(request, *args, **kwargs)
    return wrapper


def require_operator(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = get_request_user(request)
        if not user or not user.is_operator():
            return JSONResponse({"error": "Operator or Admin access required"}, status_code=403)
        return await func(request, *args, **kwargs)
    return wrapper


def require_auth(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = get_request_user(request)
        if not user:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        return await func(request, *args, **kwargs)
    return wrapper
