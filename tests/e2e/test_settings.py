# SPDX-License-Identifier: MIT
"""E2E: Settings page — page load, API endpoints, change-password/username validation."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_settings(page: Page):
    page.goto(f"{BASE_URL}/settings")
    page.wait_for_load_state("networkidle")


# ── page loads ────────────────────────────────────────────────────────────────

def test_settings_page_loads(logged_in: Page):
    """Navigating to /settings must not redirect to /login."""
    page = logged_in
    _go_settings(page)
    assert "/login" not in page.url, f"Redirected to login: {page.url}"


def test_settings_page_has_main_content(logged_in: Page):
    """Settings page must have a visible <main> element."""
    page = logged_in
    _go_settings(page)
    expect(page.locator("main")).to_be_visible(timeout=8_000)


# ── API: settings ─────────────────────────────────────────────────────────────

def test_api_settings_returns_dict(api):
    """GET /api/settings must return 200 and a JSON dict."""
    r = api("GET", "/api/settings")
    assert r["status"] == 200, f"Expected 200, got {r['status']}"
    assert isinstance(r["body"], dict), f"Expected dict, got {type(r['body'])}"


def test_api_settings_has_expected_fields(api):
    """GET /api/settings response must contain at least one known field."""
    r = api("GET", "/api/settings")
    assert r["status"] == 200
    body = r["body"]
    known_fields = ("app_env", "current_user", "default_admin_username", "database_url",
                    "minio_endpoint", "minio_bucket", "ssh_host_key_policy", "version",
                    "app_name")
    found = [f for f in known_fields if f in body]
    assert found, f"None of the expected fields found in settings response: {list(body.keys())}"


# ── API: updates ──────────────────────────────────────────────────────────────

def test_api_updates_check(api):
    """GET /api/updates/check must return 200 or 500/503, with a JSON body."""
    r = api("GET", "/api/updates/check")
    # Network unavailability may produce 500; all 2xx/5xx are acceptable
    assert r["status"] in (200, 500, 503), f"Unexpected status: {r['status']}"
    assert isinstance(r["body"], dict), f"Expected dict response, got {type(r['body'])}"


# ── API: change-username — negative cases ─────────────────────────────────────

def test_settings_change_username_wrong_password(api):
    """POST /api/auth/change-username with a wrong current_password must return 400/401/403."""
    r = api("POST", "/api/auth/change-username", {
        "current_password": "definitely-wrong-password-xyz",
        "new_username": "e2e-test-user-should-not-exist",
    })
    assert r["status"] in (400, 401, 403), (
        f"Expected 400/401/403 for wrong password, got {r['status']}: {r['body']}"
    )


# ── API: change-password — negative cases ─────────────────────────────────────

def test_settings_change_password_wrong_current(api):
    """POST /api/auth/change-password with wrong current password must return 400/401/403."""
    r = api("POST", "/api/auth/change-password", {
        "current_password": "definitely-wrong-password-xyz",
        "new_password": "new-password-e2e",
    })
    assert r["status"] in (400, 401, 403), (
        f"Expected 400/401/403 for wrong current password, got {r['status']}: {r['body']}"
    )


def test_settings_change_password_missing_fields(api):
    """POST /api/auth/change-password with empty body must return 400 or 422."""
    r = api("POST", "/api/auth/change-password", {})
    assert r["status"] in (400, 422), (
        f"Expected 400/422 for empty body, got {r['status']}: {r['body']}"
    )


# ── page quality ──────────────────────────────────────────────────────────────

def test_settings_page_no_js_errors(logged_in: Page):
    """Settings page must load without JavaScript exceptions."""
    page = logged_in
    js_errors: list[str] = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    _go_settings(page)
    page.wait_for_load_state("networkidle")

    assert not js_errors, f"JS errors on /settings page: {js_errors}"


def test_settings_page_has_password_section(logged_in: Page):
    """Settings page must include at least one password input or a change-password form."""
    page = logged_in
    _go_settings(page)

    password_area = page.locator(
        "input[type='password'], "
        "form:has(input[type='password']), "
        "section:has-text('Password'), "
        "div:has-text('Change Password'), "
        "h2:has-text('Password'), h3:has-text('Password')"
    )
    expect(password_area.first).to_be_visible(timeout=8_000)
