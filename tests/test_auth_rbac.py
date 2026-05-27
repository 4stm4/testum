# SPDX-License-Identifier: MIT
"""Comprehensive unit tests for auth, RBAC, pagination, audit, and rate-limiter."""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src/ is importable (mirrors conftest.py)
ROOT_DIR = Path(__file__).resolve().parents[1] / "src"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("FERNET_KEY", "XvgfcADXX1oKcITCS8V7iQWr9VcweqQR7H3Vc_2qsFs=")
os.environ.setdefault("APP_ENV", "testing")

from starlette.requests import Request
from starlette.testclient import TestClient

from app.models import UserRole
from app.rbac import UserContext, get_request_user, require_roles
from app.auth import get_token_from_cookie, verify_jwt_token
from app.pagination import get_pagination_params
from app.audit import log_audit
from app.rate_limiter import RateLimiterMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_request(**query_params) -> MagicMock:
    """Return a MagicMock that quacks like a starlette Request."""
    req = MagicMock(spec=Request)
    req.query_params.get = lambda key, default=None: query_params.get(key, default)
    return req


def _run(coro):
    """Execute a coroutine synchronously in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===========================================================================
# Auth — get_token_from_cookie
# ===========================================================================

def test_get_token_from_cookie_present():
    req = MagicMock(spec=Request)
    req.cookies = {"access_token": "mytoken123"}
    assert get_token_from_cookie(req) == "mytoken123"


def test_get_token_from_cookie_missing():
    req = MagicMock(spec=Request)
    req.cookies = {}
    assert get_token_from_cookie(req) is None


def test_get_token_from_cookie_other_cookies_ignored():
    req = MagicMock(spec=Request)
    req.cookies = {"session": "abc", "csrf": "xyz"}
    assert get_token_from_cookie(req) is None


# ===========================================================================
# Auth — verify_jwt_token
# ===========================================================================

def test_verify_jwt_token_valid():
    """A freshly issued token produced by the app must verify correctly."""
    from app.main import create_jwt_token
    token = create_jwt_token("user-id-1", "alice", UserRole.ADMIN)
    payload = verify_jwt_token(token)
    assert payload is not None
    assert payload["sub"] == "user-id-1"
    assert payload["username"] == "alice"


def test_verify_jwt_token_invalid_signature():
    payload = verify_jwt_token("not.a.valid.token")
    assert payload is None


def test_verify_jwt_token_garbage_string():
    payload = verify_jwt_token("garbage")
    assert payload is None


def test_verify_jwt_token_tampered():
    import base64, json
    from app.main import create_jwt_token
    token = create_jwt_token("u1", "bob", UserRole.VIEWER)
    header, body, sig = token.split(".")
    # Flip a byte in the signature
    tampered_sig = sig[:-2] + ("AA" if not sig.endswith("AA") else "BB")
    tampered = f"{header}.{body}.{tampered_sig}"
    assert verify_jwt_token(tampered) is None


# ===========================================================================
# Auth — AuthMiddleware via real app endpoints
# ===========================================================================

def test_auth_middleware_api_returns_401_without_cookie(client):
    """Unauthenticated request to a protected API endpoint returns 401.

    The ``client`` fixture sets up the DB; we then fire a cookie-free request
    against the same running app to exercise the middleware rejection path.
    """
    from app.main import app as starlette_app
    # Build a second TestClient with no cookies, sharing the already-running DB
    with TestClient(starlette_app, raise_server_exceptions=False) as unauthenticated:
        unauthenticated.cookies.clear()
        resp = unauthenticated.get("/api/keys/", allow_redirects=False)
    assert resp.status_code == 401


def test_auth_middleware_html_redirects_to_login_without_cookie(client):
    """Unauthenticated HTML request is redirected to /login."""
    from app.main import app as starlette_app
    with TestClient(starlette_app, raise_server_exceptions=False) as unauthenticated:
        unauthenticated.cookies.clear()
        resp = unauthenticated.get("/", allow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "/login" in resp.headers.get("location", "")


def test_auth_middleware_public_health_route_accessible(client):
    """The /health endpoint is public and must not require a token."""
    resp = client.get("/health")
    assert resp.status_code == 200


def test_auth_middleware_invalid_token_returns_401_for_api(client):
    """An invalid JWT cookie on an API route yields 401."""
    from app.main import app as starlette_app
    with TestClient(starlette_app, raise_server_exceptions=False) as c:
        c.cookies.set("access_token", "invalid.token.value")
        resp = c.get("/api/keys/", allow_redirects=False)
    assert resp.status_code == 401


def test_auth_middleware_authenticated_client_gets_200(client):
    """The pre-authenticated admin client can reach protected API routes."""
    resp = client.get("/api/keys/")
    assert resp.status_code == 200


# ===========================================================================
# RBAC — UserContext permission methods
# ===========================================================================

def test_usercontext_admin_is_admin():
    u = UserContext(id="1", username="alice", role=UserRole.ADMIN)
    assert u.is_admin() is True


def test_usercontext_operator_is_not_admin():
    u = UserContext(id="2", username="bob", role=UserRole.OPERATOR)
    assert u.is_admin() is False


def test_usercontext_admin_is_operator():
    u = UserContext(id="1", username="alice", role=UserRole.ADMIN)
    assert u.is_operator() is True


def test_usercontext_operator_is_operator():
    u = UserContext(id="2", username="bob", role=UserRole.OPERATOR)
    assert u.is_operator() is True


def test_usercontext_viewer_is_not_operator():
    u = UserContext(id="3", username="carol", role=UserRole.VIEWER)
    assert u.is_operator() is False


def test_usercontext_viewer_is_viewer():
    u = UserContext(id="3", username="carol", role=UserRole.VIEWER)
    assert u.is_viewer() is True


def test_usercontext_admin_can_write():
    u = UserContext(id="1", username="alice", role=UserRole.ADMIN)
    assert u.can_write() is True


def test_usercontext_operator_can_write():
    u = UserContext(id="2", username="bob", role=UserRole.OPERATOR)
    assert u.can_write() is True


def test_usercontext_viewer_cannot_write():
    u = UserContext(id="3", username="carol", role=UserRole.VIEWER)
    assert u.can_write() is False


def test_usercontext_viewer_can_read():
    u = UserContext(id="3", username="carol", role=UserRole.VIEWER)
    assert u.can_read() is True


def test_usercontext_admin_has_any_role_admin():
    u = UserContext(id="1", username="alice", role=UserRole.ADMIN)
    # Admin always passes regardless of the role list
    assert u.has_any_role([UserRole.VIEWER]) is True


def test_usercontext_operator_has_any_role_match():
    u = UserContext(id="2", username="bob", role=UserRole.OPERATOR)
    assert u.has_any_role([UserRole.OPERATOR, UserRole.ADMIN]) is True


def test_usercontext_viewer_has_any_role_no_match():
    u = UserContext(id="3", username="carol", role=UserRole.VIEWER)
    assert u.has_any_role([UserRole.OPERATOR, UserRole.ADMIN]) is False


# ===========================================================================
# RBAC — get_request_user
# ===========================================================================

def test_get_request_user_returns_context_when_set():
    req = MagicMock(spec=Request)
    ctx = UserContext(id="1", username="alice", role=UserRole.ADMIN)
    req.state.user = ctx
    assert get_request_user(req) is ctx


def test_get_request_user_returns_none_when_absent():
    req = MagicMock(spec=Request)
    # Remove the 'user' attribute from state so getattr returns None
    del req.state.user
    result = get_request_user(req)
    assert result is None


# ===========================================================================
# RBAC — require_roles decorator
# ===========================================================================

def test_require_roles_allows_matching_role():
    """Handler is called when the user has the required role."""
    called = []

    @require_roles(UserRole.ADMIN)
    async def handler(request):
        called.append(True)
        return MagicMock(status_code=200)

    req = MagicMock(spec=Request)
    req.state.user = UserContext(id="1", username="alice", role=UserRole.ADMIN)
    _run(handler(req))
    assert called == [True]


def test_require_roles_returns_403_when_role_missing():
    """Handler returns 403 when the user lacks the required role."""
    @require_roles(UserRole.ADMIN)
    async def handler(request):
        return MagicMock(status_code=200)

    req = MagicMock(spec=Request)
    req.state.user = UserContext(id="3", username="carol", role=UserRole.VIEWER)
    response = _run(handler(req))
    assert response.status_code == 403


def test_require_roles_returns_403_when_no_user():
    """Handler returns 403 when no user is present on the request."""
    @require_roles(UserRole.OPERATOR)
    async def handler(request):
        return MagicMock(status_code=200)

    req = MagicMock(spec=Request)
    # Make state.user absent
    type(req.state).user = property(lambda self: None)
    response = _run(handler(req))
    assert response.status_code == 403


def test_require_roles_operator_allowed_for_operator_role():
    """Operator user passes require_roles(OPERATOR)."""
    results = []

    @require_roles(UserRole.OPERATOR)
    async def handler(request):
        results.append("ok")
        return MagicMock(status_code=200)

    req = MagicMock(spec=Request)
    req.state.user = UserContext(id="2", username="bob", role=UserRole.OPERATOR)
    _run(handler(req))
    assert results == ["ok"]


# ===========================================================================
# Pagination — get_pagination_params
# ===========================================================================

def test_pagination_valid_params():
    req = _make_mock_request(limit="50", offset="0")
    limit, offset = get_pagination_params(req)
    assert limit == 50
    assert offset == 0


def test_pagination_defaults_when_no_params():
    req = _make_mock_request()
    limit, offset = get_pagination_params(req, default_limit=25)
    assert limit == 25
    assert offset == 0


def test_pagination_negative_limit_raises():
    req = _make_mock_request(limit="-1", offset="0")
    with pytest.raises(ValueError, match="limit"):
        get_pagination_params(req)


def test_pagination_zero_limit_raises():
    req = _make_mock_request(limit="0", offset="0")
    with pytest.raises(ValueError):
        get_pagination_params(req)


def test_pagination_negative_offset_raises():
    req = _make_mock_request(limit="10", offset="-5")
    with pytest.raises(ValueError, match="offset"):
        get_pagination_params(req)


def test_pagination_limit_clamped_to_max():
    req = _make_mock_request(limit="9999", offset="0")
    limit, _ = get_pagination_params(req, max_limit=100)
    assert limit == 100


def test_pagination_non_integer_limit_raises():
    req = _make_mock_request(limit="abc", offset="0")
    with pytest.raises(ValueError):
        get_pagination_params(req)


def test_pagination_non_integer_offset_raises():
    req = _make_mock_request(limit="10", offset="xyz")
    with pytest.raises(ValueError):
        get_pagination_params(req)


def test_pagination_limit_exactly_at_max_not_clamped():
    req = _make_mock_request(limit="200", offset="10")
    limit, offset = get_pagination_params(req, max_limit=200)
    assert limit == 200
    assert offset == 10


def test_pagination_large_offset_allowed():
    req = _make_mock_request(limit="10", offset="10000")
    limit, offset = get_pagination_params(req)
    assert offset == 10000


# ===========================================================================
# Audit — log_audit
# ===========================================================================

def test_log_audit_creates_row(test_db):
    entry = log_audit(test_db, "alice", "create", "ssh_key", object_id="key-1")
    assert entry is not None
    assert entry.user == "alice"
    assert entry.action == "create"
    assert entry.object_type == "ssh_key"
    assert entry.object_id == "key-1"


def test_log_audit_none_meta_is_ok(test_db):
    entry = log_audit(test_db, "bob", "delete", "platform", meta=None)
    assert entry.meta is None


def test_log_audit_dict_meta_stored(test_db):
    meta = {"reason": "scheduled", "count": 3}
    entry = log_audit(test_db, "alice", "update", "task", meta=meta)
    assert entry.meta == meta


def test_log_audit_uuid_in_meta_serialized(test_db):
    """UUID values inside meta must not raise a serialisation error."""
    some_uuid = uuid.uuid4()
    entry = log_audit(
        test_db,
        "alice",
        "create",
        "vm",
        object_id="vm-99",
        meta={"vm_id": some_uuid},
    )
    # The stored value should be a string representation of the UUID
    assert entry.meta is not None
    assert str(some_uuid) in str(entry.meta["vm_id"])


def test_log_audit_datetime_in_meta_serialized(test_db):
    """datetime values inside meta must not raise a serialisation error."""
    now = datetime.utcnow()
    entry = log_audit(
        test_db,
        "carol",
        "read",
        "report",
        meta={"generated_at": now},
    )
    assert entry.meta is not None
    assert entry.meta["generated_at"] is not None


def test_log_audit_returns_audit_log_instance(test_db):
    from app.models import AuditLog
    entry = log_audit(test_db, "dave", "login", "session")
    assert isinstance(entry, AuditLog)


def test_log_audit_persisted_to_db(test_db):
    """The AuditLog row must be queryable after log_audit returns."""
    from app.models import AuditLog
    log_audit(test_db, "eve", "export", "keys", object_id="all")
    row = test_db.query(AuditLog).filter_by(user="eve", action="export").first()
    assert row is not None


# ===========================================================================
# Rate limiter — RateLimiterMiddleware
# ===========================================================================

def _make_rate_limit_app(limit: int = 3, window_seconds: int = 60):
    """Build a minimal Starlette app wrapped with RateLimiterMiddleware."""
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route

    async def homepage(request):
        return PlainTextResponse("ok")

    inner = Starlette(routes=[Route("/", homepage)])
    return RateLimiterMiddleware(inner, limit=limit, window_seconds=window_seconds)


def test_rate_limiter_allows_requests_under_limit():
    """Requests below the limit all return 200."""
    wrapped = _make_rate_limit_app(limit=5)
    with TestClient(wrapped) as c:
        for _ in range(5):
            resp = c.get("/")
            assert resp.status_code == 200


def test_rate_limiter_returns_429_when_limit_exceeded():
    """The (limit+1)-th request receives 429."""
    wrapped = _make_rate_limit_app(limit=3)
    with TestClient(wrapped) as c:
        for _ in range(3):
            c.get("/")
        resp = c.get("/")
        assert resp.status_code == 429


def test_rate_limiter_429_has_retry_after_header():
    """429 response must include Retry-After header."""
    wrapped = _make_rate_limit_app(limit=2)
    with TestClient(wrapped) as c:
        c.get("/")
        c.get("/")
        resp = c.get("/")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) >= 1


def test_rate_limiter_200_includes_ratelimit_headers():
    """Responses under the limit include X-RateLimit-* informational headers."""
    wrapped = _make_rate_limit_app(limit=10)
    with TestClient(wrapped) as c:
        resp = c.get("/")
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers


def test_rate_limiter_429_error_body():
    """429 JSON body must contain the 'error' key."""
    wrapped = _make_rate_limit_app(limit=1)
    with TestClient(wrapped) as c:
        c.get("/")
        resp = c.get("/")
    assert resp.status_code == 429
    body = resp.json()
    assert "error" in body
