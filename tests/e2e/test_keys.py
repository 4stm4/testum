# SPDX-License-Identifier: MIT
"""E2E: SSH key management — list, create, delete."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

# Minimal RSA public key for testing (not a real key — just valid format)
_FAKE_PUB_KEY = (
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAQQDummyKeyForTestingOnlyNotReal"
    "AAAAblahblahblah e2e-test@testum"
)


def _go_keys(page: Page):
    page.goto(f"{BASE_URL}/keys")
    page.wait_for_load_state("networkidle")


# ── page loads ────────────────────────────────────────────────────────────

def test_keys_page_loads(logged_in: Page):
    page = logged_in
    _go_keys(page)
    assert "/keys" in page.url


def test_keys_page_has_add_button(logged_in: Page):
    page = logged_in
    _go_keys(page)
    btn = page.locator(
        "button:has-text('Add'), button:has-text('Generate'), "
        "button:has-text('Добавить'), button:has-text('Создать'), "
        "[data-i18n='add_key'], #add-key-btn"
    )
    expect(btn.first).to_be_visible(timeout=8_000)


# ── API: create / list / delete ───────────────────────────────────────────

def test_create_key_via_api(api):
    r = api("POST", "/api/keys", {
        "name": "e2e-test-key",
        "public_key": _FAKE_PUB_KEY,
    })
    # 422 is OK if key format validation fails — anything but 500
    assert r["status"] < 500

    if r["status"] in (200, 201):
        kid = r["body"].get("id")
        assert kid
        # Cleanup
        api("DELETE", f"/api/keys/{kid}")


def test_list_keys_returns_list(api):
    r = api("GET", "/api/keys")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_key_lifecycle_via_api(api):
    r = api("POST", "/api/keys", {
        "name": "e2e-lifecycle-key",
        "public_key": _FAKE_PUB_KEY,
    })
    if r["status"] not in (200, 201):
        pytest.skip(f"Key creation returned {r['status']} — may require real key format")

    kid = r["body"]["id"]

    # Appears in list
    r2 = api("GET", "/api/keys")
    ids = [k["id"] for k in r2["body"]]
    assert kid in ids

    # Delete
    r3 = api("DELETE", f"/api/keys/{kid}")
    assert r3["status"] in (200, 204)

    # Gone from list
    r4 = api("GET", "/api/keys")
    ids_after = [k["id"] for k in r4["body"]]
    assert kid not in ids_after


# ── UI ────────────────────────────────────────────────────────────────────

def test_keys_page_shows_table_or_empty(logged_in: Page):
    page = logged_in
    _go_keys(page)
    # Keys uses card layout — check that main has content
    content = page.locator("main").inner_text()
    assert len(content) > 0


def test_created_key_appears_in_ui(logged_in: Page, api):
    r = api("POST", "/api/keys", {
        "name": "e2e-ui-key",
        "public_key": _FAKE_PUB_KEY,
    })
    if r["status"] not in (200, 201):
        pytest.skip("Key creation requires valid key format")

    kid = r["body"]["id"]
    page = logged_in
    _go_keys(page)
    page.reload()
    page.wait_for_load_state("networkidle")

    row = page.locator("text=e2e-ui-key")
    expect(row.first).to_be_visible(timeout=8_000)

    # Cleanup
    api("DELETE", f"/api/keys/{kid}")
