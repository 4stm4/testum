# SPDX-License-Identifier: MIT
"""E2E: User management — list, create, update role, delete."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_users(page: Page):
    page.goto(f"{BASE_URL}/users")
    page.wait_for_load_state("networkidle")


def _users_list(api) -> list:
    """GET /api/users — handles both plain list and {items:[...]} shapes."""
    r = api("GET", "/api/users")
    assert r["status"] == 200
    body = r["body"]
    if isinstance(body, list):
        return body
    return body.get("items", [])


# ── page loads ────────────────────────────────────────────────────────────

def test_users_page_loads(logged_in: Page):
    page = logged_in
    _go_users(page)
    assert "/users" in page.url


def test_users_page_lists_admin(logged_in: Page):
    page = logged_in
    _go_users(page)
    admin_row = page.locator("text=admin")
    expect(admin_row.first).to_be_visible(timeout=8_000)


# ── create user ───────────────────────────────────────────────────────────

def test_create_user_via_api(api):
    import uuid
    uname = f"e2e-user-{uuid.uuid4().hex[:6]}"
    r = api("POST", "/api/users", {
        "username": uname,
        "password": "TestPass123!",
        "role": "viewer",
    })
    assert r["status"] in (200, 201), f"Create user failed: {r}"
    uid = r["body"].get("id")
    assert uid
    api("DELETE", f"/api/users/{uid}")


def test_users_page_has_create_button(logged_in: Page):
    page = logged_in
    _go_users(page)
    btn = page.locator(
        "button:has-text('Add'), button:has-text('Create'), "
        "button:has-text('Создать'), button:has-text('Добавить'), "
        "[data-i18n='add_user'], #add-user-btn"
    )
    expect(btn.first).to_be_visible(timeout=8_000)


def test_create_user_appears_in_list(logged_in: Page, api):
    import uuid
    uname = f"e2e-vis-{uuid.uuid4().hex[:6]}"
    r = api("POST", "/api/users", {
        "username": uname,
        "password": "TestPass123!",
        "role": "viewer",
    })
    if r["status"] not in (200, 201):
        pytest.skip("Cannot create user via API")

    uid = r["body"]["id"]
    page = logged_in
    _go_users(page)
    page.reload()
    page.wait_for_load_state("networkidle")
    expect(page.locator(f"text={uname}").first).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/users/{uid}")


# ── update role ───────────────────────────────────────────────────────────

def test_update_user_role_via_api(api):
    import uuid
    uname = f"e2e-role-{uuid.uuid4().hex[:6]}"
    r = api("POST", "/api/users", {
        "username": uname,
        "password": "TestPass123!",
        "role": "viewer",
    })
    if r["status"] not in (200, 201):
        pytest.skip("Cannot create user via API")
    uid = r["body"]["id"]

    r2 = api("PUT", f"/api/users/{uid}", {"role": "operator"})
    assert r2["status"] == 200
    assert r2["body"].get("role") == "operator"
    api("DELETE", f"/api/users/{uid}")


# ── delete user ───────────────────────────────────────────────────────────

def test_delete_user_via_api(api):
    import uuid
    uname = f"e2e-del-{uuid.uuid4().hex[:6]}"
    r = api("POST", "/api/users", {
        "username": uname,
        "password": "TestPass123!",
        "role": "viewer",
    })
    if r["status"] not in (200, 201):
        pytest.skip("Cannot create user via API")
    uid = r["body"]["id"]

    r2 = api("DELETE", f"/api/users/{uid}")
    assert r2["status"] in (200, 204)

    ids = [u["id"] for u in _users_list(api)]
    assert uid not in ids


def test_delete_user_disappears_from_ui(logged_in: Page, api):
    import uuid
    uname = f"e2e-gone-{uuid.uuid4().hex[:6]}"
    r = api("POST", "/api/users", {
        "username": uname,
        "password": "TestPass123!",
        "role": "viewer",
    })
    if r["status"] not in (200, 201):
        pytest.skip("Cannot create user via API")
    uid = r["body"]["id"]
    api("DELETE", f"/api/users/{uid}")

    page = logged_in
    _go_users(page)
    expect(page.locator(f"text={uname}")).to_have_count(0, timeout=5_000)


# ── get current user ──────────────────────────────────────────────────────

def test_get_current_user_api(api):
    r = api("GET", "/api/users/me")
    assert r["status"] == 200
    assert "username" in r["body"]
    assert r["body"]["username"] == "admin"
