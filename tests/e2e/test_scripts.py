# SPDX-License-Identifier: MIT
"""E2E: Scripts — CRUD via API and UI."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_scripts(page: Page):
    page.goto(f"{BASE_URL}/scripts")
    page.wait_for_load_state("networkidle")


# ── page loads ────────────────────────────────────────────────────────────

def test_scripts_page_loads(logged_in: Page):
    page = logged_in
    _go_scripts(page)
    assert "/scripts" in page.url


def test_scripts_page_has_create_button(logged_in: Page):
    page = logged_in
    _go_scripts(page)
    btn = page.locator(
        "button:has-text('Add'), button:has-text('Create'), "
        "button:has-text('New'), button:has-text('Создать'), "
        "button:has-text('Добавить'), [data-i18n='add_script'], #add-script-btn"
    )
    expect(btn.first).to_be_visible(timeout=8_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────

def test_list_scripts_returns_list(api):
    r = api("GET", "/api/scripts")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_create_script_via_api(api):
    r = api("POST", "/api/scripts", {
        "name": "e2e-script",
        "description": "E2E test script",
        "content": "#!/bin/bash\necho hello",
        "script_type": "bash",
    })
    assert r["status"] in (200, 201), f"Create script failed: {r}"
    sid = r["body"].get("id")
    assert sid

    # Cleanup
    api("DELETE", f"/api/scripts/{sid}")


def test_get_script_via_api(api):
    r = api("POST", "/api/scripts", {
        "name": "e2e-get-script",
        "content": "echo world",
    })
    if r["status"] not in (200, 201):
        pytest.skip("Script creation failed")
    sid = r["body"]["id"]

    r2 = api("GET", f"/api/scripts/{sid}")
    assert r2["status"] == 200
    assert r2["body"]["id"] == sid

    api("DELETE", f"/api/scripts/{sid}")


def test_update_script_via_api(api):
    r = api("POST", "/api/scripts", {
        "name": "e2e-upd-script",
        "content": "echo original",
    })
    if r["status"] not in (200, 201):
        pytest.skip("Script creation failed")
    sid = r["body"]["id"]

    r2 = api("PUT", f"/api/scripts/{sid}", {
        "name": "e2e-upd-script",
        "content": "echo updated",
    })
    assert r2["status"] == 200
    assert "updated" in r2["body"].get("content", "")

    api("DELETE", f"/api/scripts/{sid}")


def test_delete_script_via_api(api):
    r = api("POST", "/api/scripts", {
        "name": "e2e-del-script",
        "content": "echo delete me",
    })
    if r["status"] not in (200, 201):
        pytest.skip("Script creation failed")
    sid = r["body"]["id"]

    r2 = api("DELETE", f"/api/scripts/{sid}")
    assert r2["status"] in (200, 204)

    r3 = api("GET", f"/api/scripts/{sid}")
    assert r3["status"] == 404


def test_get_script_not_found(api):
    import uuid
    r = api("GET", f"/api/scripts/{uuid.uuid4()}")
    assert r["status"] == 404


# ── UI ────────────────────────────────────────────────────────────────────

def test_scripts_page_shows_table_or_empty(logged_in: Page):
    page = logged_in
    _go_scripts(page)
    # Scripts uses card layout — check that main has some content
    content = page.locator("main").inner_text()
    assert len(content) > 0


def test_created_script_appears_in_ui(logged_in: Page, api):
    r = api("POST", "/api/scripts", {
        "name": "e2e-ui-script",
        "content": "echo visible",
    })
    if r["status"] not in (200, 201):
        pytest.skip("Script creation failed")

    sid = r["body"]["id"]
    page = logged_in
    _go_scripts(page)
    page.reload()
    page.wait_for_load_state("networkidle")

    row = page.locator("text=e2e-ui-script")
    expect(row.first).to_be_visible(timeout=8_000)

    api("DELETE", f"/api/scripts/{sid}")
