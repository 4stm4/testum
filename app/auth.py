"""Authentication middleware and utilities."""
import logging
from typing import Optional

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.config import config
from app import db as app_db
from app.models import User, UserRole
from app.rbac import UserContext

logger = logging.getLogger(__name__)


def get_token_from_cookie(request: Request) -> Optional[str]:
    """Extract JWT token from cookie."""
    return request.cookies.get("access_token")


def verify_jwt_token(token: str) -> Optional[dict]:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid token")
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to check authentication for protected routes."""
    
    # Public routes that don't require authentication
    PUBLIC_ROUTES = {
        "/login",
        "/api/auth/login",
        "/health",
        "/docs",
        "/openapi.json",
    }
    
    async def dispatch(self, request: Request, call_next):
        """Check authentication before processing request."""
        path = request.url.path
        
        # Allow public routes
        if path in self.PUBLIC_ROUTES or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)
        
        # Get token from cookie
        token = get_token_from_cookie(request)
        
        if not token:
            # No token - redirect to login for HTML pages, 401 for API
            if path.startswith("/api/"):
                return Response(
                    content='{"error": "Authentication required"}',
                    status_code=401,
                    media_type="application/json"
                )
            else:
                return RedirectResponse(url="/login", status_code=302)
        
        # Verify token
        payload = verify_jwt_token(token)
        if not payload:
            # Invalid/expired token - redirect to login for HTML pages, 401 for API
            if path.startswith("/api/"):
                return Response(
                    content='{"error": "Invalid or expired token"}',
                    status_code=401,
                    media_type="application/json"
                )
            else:
                # Clear invalid cookie
                response = RedirectResponse(url="/login", status_code=302)
                response.delete_cookie("access_token")
                return response
        
        user_id = payload.get("sub")
        if not user_id:
            return Response(
                content='{"error": "Invalid token payload"}',
                status_code=401,
                media_type="application/json",
            )
        
        # Convert user_id to UUID if it's a string
        try:
            if isinstance(user_id, str):
                import uuid as uuid_module
                user_id_uuid = uuid_module.UUID(user_id)
            else:
                user_id_uuid = user_id
        except (ValueError, AttributeError):
            return Response(
                content='{"error": "Invalid user ID in token"}',
                status_code=401,
                media_type="application/json",
            )

        with app_db.SessionLocal() as db:
            user = db.query(User).filter(User.id == user_id_uuid).first()

            if not user or not user.is_active:
                if path.startswith("/api/"):
                    return Response(
                        content='{"error": "User inactive or not found"}',
                        status_code=403,
                        media_type="application/json",
                    )
                response = RedirectResponse(url="/login", status_code=302)
                response.delete_cookie("access_token")
                return response

            request.state.user = UserContext(
                id=str(user.id),
                username=user.username,
                role=user.role if isinstance(user.role, UserRole) else UserRole(user.role),
            )

        # Continue processing request
        return await call_next(request)
