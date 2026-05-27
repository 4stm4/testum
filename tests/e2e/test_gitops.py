# SPDX-License-Identifier: MIT
"""E2E: GitOps import API — /api/gitops/import.

The gitops router exposes a single route:
    POST /api/gitops/import  — clone a Git repo and import platforms/keys.

Tests cover the happy and error paths reachable without a real Git server.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

from .conftest import BASE_URL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post_gitops_import(page: Page, body: dict) -> dict:
    """POST /api/gitops/import with a JSON body, return {status, body}."""
    import json as _json
    body_js = _json.dumps(body)
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/gitops/import')!r}, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({body_js}),
        }});
        return {{status: r.status, body: await r.json().catch(() => ({{}}))}};
    }}
    """)
    return result


# ---------------------------------------------------------------------------
# Route reachability
# ---------------------------------------------------------------------------

def test_gitops_import_endpoint_exists(logged_in):
    """POST /api/gitops/import with no body returns something other than 404/405."""
    result = _post_gitops_import(logged_in, {})
    # 400 (missing git_url) or 500 are acceptable; 404/405 would mean route is missing
    assert result["status"] not in (404, 405), (
        f"Gitops import route not found or method not allowed: {result['status']}"
    )


def test_gitops_import_missing_git_url_returns_400(api):
    """POST /api/gitops/import without git_url → 400."""
    r = api("POST", "/api/gitops/import", {})
    assert r["status"] == 400
    assert "git_url" in str(r["body"]).lower()


def test_gitops_import_error_message_is_string(api):
    """Error response body has an 'error' key that is a string."""
    r = api("POST", "/api/gitops/import", {})
    assert r["status"] == 400
    assert isinstance(r["body"].get("error"), str)


# ---------------------------------------------------------------------------
# Invalid / unreachable git_url
# ---------------------------------------------------------------------------

def test_gitops_import_invalid_git_url_returns_400(api):
    """POST /api/gitops/import with a garbage URL → 400 (clone fails)."""
    r = api("POST", "/api/gitops/import", {
        "git_url": "https://invalid.example.invalid/repo.git",
        "branch": "main",
    })
    assert r["status"] in (400, 500), (
        f"Expected 400 or 500 for unreachable URL, got {r['status']}"
    )


def test_gitops_import_localhost_git_url_returns_400_or_500(api):
    """POST /api/gitops/import pointing at localhost (no server) → 400 or 500."""
    r = api("POST", "/api/gitops/import", {
        "git_url": "https://localhost:19999/does-not-exist.git",
    })
    assert r["status"] in (400, 500)


def test_gitops_import_error_body_is_dict(api):
    """Any error response must be a JSON object, not a list or scalar."""
    r = api("POST", "/api/gitops/import", {
        "git_url": "https://invalid.example.invalid/repo.git",
    })
    assert isinstance(r["body"], dict), f"Expected dict, got: {type(r['body'])} — {r['body']}"


def test_gitops_import_dry_run_flag_accepted(api):
    """dry_run=true is accepted in the request body (no schema error)."""
    r = api("POST", "/api/gitops/import", {
        "git_url": "https://invalid.example.invalid/repo.git",
        "dry_run": True,
    })
    # 400/500 because clone will fail, but should NOT be a schema/validation error
    assert r["status"] in (400, 500)
    # Must not complain about unexpected field 'dry_run'
    error_text = str(r["body"]).lower()
    assert "dry_run" not in error_text or "git" in error_text, (
        f"Server rejected dry_run as unknown field: {r['body']}"
    )


def test_gitops_import_branch_field_accepted(api):
    """branch field is accepted without schema error."""
    r = api("POST", "/api/gitops/import", {
        "git_url": "https://invalid.example.invalid/repo.git",
        "branch": "develop",
    })
    assert r["status"] in (400, 500)
    error_text = str(r["body"]).lower()
    assert "branch" not in error_text or "git" in error_text


def test_gitops_import_config_path_field_accepted(api):
    """config_path field is accepted without schema error."""
    r = api("POST", "/api/gitops/import", {
        "git_url": "https://invalid.example.invalid/repo.git",
        "config_path": "infrastructure/testum.yaml",
    })
    assert r["status"] in (400, 500)


def test_gitops_import_requires_auth(page: Page):
    """Unauthenticated POST /api/gitops/import → 401 or 403 (not 200)."""
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/gitops/import')!r}, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{"git_url": "https://example.com/repo.git"}}),
        }});
        return {{status: r.status}};
    }}
    """)
    assert result["status"] in (401, 403), (
        f"Expected 401/403 for unauthenticated request, got {result['status']}"
    )


def test_gitops_import_other_methods_not_allowed(logged_in):
    """GET /api/gitops/import → 405 or 404 (method not allowed)."""
    page = logged_in
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/gitops/import')!r}, {{
            method: 'GET',
        }});
        return {{status: r.status}};
    }}
    """)
    assert result["status"] in (404, 405), (
        f"Expected 404/405 for GET on import endpoint, got {result['status']}"
    )


def test_gitops_import_with_token_field_accepted(api):
    """username + token fields are accepted (no schema rejection)."""
    r = api("POST", "/api/gitops/import", {
        "git_url": "https://invalid.example.invalid/repo.git",
        "username": "git",
        "token": "sometoken",
    })
    assert r["status"] in (400, 500)
    # Should not complain about unknown fields
    error_text = str(r["body"]).lower()
    assert "token" not in error_text or "git" in error_text
