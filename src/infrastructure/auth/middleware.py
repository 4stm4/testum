# SPDX-License-Identifier: MIT
"""JWT authentication middleware."""
from __future__ import annotations

import logging
import uuid as uuid_module
from typing import Optional

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from core.domain.enums import UserRole
from core.interfaces.storage import Storage
from infrastructure.auth.rbac import UserContext
from infrastructure.config import config

logger = logging.getLogger(__name__)

PUBLIC_ROUTES = {
    "/login",
    "/api/auth/login",
    "/health",
    "/docs",
    "/openapi.json",
}


def _decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        logger.warning("JWT expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("JWT invalid")
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, storage: Storage) -> None:
        super().__init__(app)
        self._storage = storage

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in PUBLIC_ROUTES or path.startswith(("/docs", "/openapi", "/static")):
            return await call_next(request)

        token = request.cookies.get("access_token")
        if not token:
            return self._unauth(request, "Authentication required")

        payload = _decode_token(token)
        if not payload:
            resp = self._unauth(request, "Invalid or expired token")
            resp.delete_cookie("access_token")
            return resp

        user_id_raw = payload.get("sub")
        try:
            user_id = str(uuid_module.UUID(str(user_id_raw)))
        except (ValueError, AttributeError):
            return self._unauth(request, "Invalid user ID in token")

        user = self._storage.get_user_by_id(user_id)
        if not user or not user.is_active:
            resp = self._unauth(request, "User not found or inactive")
            resp.delete_cookie("access_token")
            return resp

        request.state.user = UserContext(
            id=user.id,
            username=user.username,
            role=UserRole(user.role.value if hasattr(user.role, "value") else user.role),
        )
        return await call_next(request)

    @staticmethod
    def _unauth(request: Request, message: str) -> Response:
        if request.url.path.startswith("/api/"):
            return Response(
                content=f'{{"error": "{message}"}}',
                status_code=401,
                media_type="application/json",
            )
        return RedirectResponse(url="/login", status_code=302)
