"""Authentication middleware and utilities."""
import logging
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
import jwt

from app.config import config

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
        
        # Add user info to request state
        request.state.user = payload.get("sub")
        
        # Continue processing request
        return await call_next(request)
