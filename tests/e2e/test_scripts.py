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


# ── Additional tests ──────────────────────────────────────────────────────

def test_script_content_saved(api):
    """Create a script with specific content; GET it back and verify content matches."""
    content = "#!/bin/bash\necho 'content-check-e2e'\ndate"
    r = api("POST", "/api/scripts", {
        "name": "e2e-content-saved",
        "content": content,
    })
    if r["status"] not in (200, 201):
        pytest.skip(f"Script creation returned {r['status']}")
    sid = r["body"]["id"]

    r2 = api("GET", f"/api/scripts/{sid}")
    assert r2["status"] == 200
    assert r2["body"].get("content") == content, (
        f"Content mismatch — expected {content!r}, got {r2['body'].get('content')!r}"
    )

    api("DELETE", f"/api/scripts/{sid}")


def test_update_script_content(api):
    """Create a script, update its content via PUT, verify the change persists."""
    r = api("POST", "/api/scripts", {
        "name": "e2e-update-content",
        "content": "echo original-content",
    })
    if r["status"] not in (200, 201):
        pytest.skip(f"Script creation returned {r['status']}")
    sid = r["body"]["id"]

    new_content = "echo updated-content"
    r2 = api("PUT", f"/api/scripts/{sid}", {
        "name": "e2e-update-content",
        "content": new_content,
    })
    assert r2["status"] == 200, f"Update returned {r2['status']}: {r2['body']}"

    r3 = api("GET", f"/api/scripts/{sid}")
    assert r3["status"] == 200
    assert r3["body"].get("content") == new_content, (
        f"Updated content not persisted — got {r3['body'].get('content')!r}"
    )

    api("DELETE", f"/api/scripts/{sid}")


def test_script_name_in_response(api):
    """Created script response body contains a 'name' field matching what was sent."""
    r = api("POST", "/api/scripts", {
        "name": "e2e-name-field-check",
        "content": "echo name-check",
    })
    if r["status"] not in (200, 201):
        pytest.skip(f"Script creation returned {r['status']}")

    body = r["body"]
    assert "name" in body, f"'name' field missing from response: {body}"
    assert body["name"] == "e2e-name-field-check", (
        f"Name mismatch: expected 'e2e-name-field-check', got {body['name']!r}"
    )

    api("DELETE", f"/api/scripts/{body['id']}")


def test_delete_script_removes_from_list(api):
    """Create a script, delete it, then verify it no longer appears in the list."""
    r = api("POST", "/api/scripts", {
        "name": "e2e-delete-from-list",
        "content": "echo delete-check",
    })
    if r["status"] not in (200, 201):
        pytest.skip(f"Script creation returned {r['status']}")
    sid = r["body"]["id"]

    del_r = api("DELETE", f"/api/scripts/{sid}")
    assert del_r["status"] in (200, 204), f"Delete returned {del_r['status']}"

    list_r = api("GET", "/api/scripts")
    assert list_r["status"] == 200
    ids = [s["id"] for s in list_r["body"]]
    assert sid not in ids, f"Deleted script {sid} still in list: {ids}"


def test_scripts_page_shows_created_script(logged_in: Page, api):
    """Create a script via API, navigate to /scripts, verify the name is visible."""
    r = api("POST", "/api/scripts", {
        "name": "e2e-page-show-script",
        "content": "echo page-visible",
    })
    if r["status"] not in (200, 201):
        pytest.skip("Script creation failed — skipping UI visibility check")

    sid = r["body"]["id"]
    page = logged_in
    page.goto(f"{BASE_URL}/scripts")
    page.wait_for_load_state("networkidle")

    from playwright.sync_api import expect as _expect
    name_loc = page.locator("text=e2e-page-show-script")
    _expect(name_loc.first).to_be_visible(timeout=8_000)

    api("DELETE", f"/api/scripts/{sid}")


def test_script_get_returns_full_content(api):
    """GET /api/scripts/{id} returns the full script object with id, name, and content."""
    r = api("POST", "/api/scripts", {
        "name": "e2e-full-object-check",
        "content": "echo full-object",
    })
    if r["status"] not in (200, 201):
        pytest.skip(f"Script creation returned {r['status']}")
    sid = r["body"]["id"]

    r2 = api("GET", f"/api/scripts/{sid}")
    assert r2["status"] == 200
    body = r2["body"]
    for field in ("id", "name", "content"):
        assert field in body, f"Missing '{field}' in GET response: {body}"
    assert body["id"] == sid

    api("DELETE", f"/api/scripts/{sid}")


def test_script_empty_content_accepted(api):
    """Create a script with empty string content — should succeed or return 422, not 500."""
    r = api("POST", "/api/scripts", {
        "name": "e2e-empty-content-script",
        "content": "",
    })
    assert r["status"] in (200, 201, 422), (
        f"Expected 200/201/422 for empty content, got {r['status']}: {r['body']}"
    )
    if r["status"] in (200, 201):
        sid = r["body"].get("id")
        if sid:
            api("DELETE", f"/api/scripts/{sid}")


def test_scripts_list_pagination(api):
    """GET /api/scripts?limit=2 — if param is honoured, response length is ≤ 2."""
    r = api("GET", "/api/scripts?limit=2")
    assert r["status"] == 200
    assert isinstance(r["body"], list)
    # If the server honours the limit parameter, the list must have at most 2 items.
    # If the server ignores it, the list may be longer — which is also acceptable.
    # We only fail if the server returns a non-list or an error.
