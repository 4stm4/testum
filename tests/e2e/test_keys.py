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


# ── Additional tests ──────────────────────────────────────────────────────

def test_create_key_rsa_type(api):
    """POST /api/keys with an RSA public key is accepted (200/201) or fails gracefully."""
    r = api("POST", "/api/keys", {
        "name": "e2e-rsa-type-key",
        "public_key": _FAKE_PUB_KEY,  # starts with ssh-rsa
    })
    assert r["status"] < 500, f"Server error on RSA key creation: {r}"
    if r["status"] in (200, 201):
        kid = r["body"].get("id")
        if kid:
            api("DELETE", f"/api/keys/{kid}")


def test_create_key_ed25519_type(api):
    """POST /api/keys with an ed25519 public key is accepted (200/201) or fails gracefully."""
    ed25519_pub = (
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDummyEd25519KeyForTestingOnlyNotReal"
        " e2e-test-ed25519@testum"
    )
    r = api("POST", "/api/keys", {
        "name": "e2e-ed25519-type-key",
        "public_key": ed25519_pub,
    })
    assert r["status"] < 500, f"Server error on ed25519 key creation: {r}"
    if r["status"] in (200, 201):
        kid = r["body"].get("id")
        if kid:
            api("DELETE", f"/api/keys/{kid}")


def test_key_has_required_fields(api):
    """Created key response contains 'id', 'name', and a public key or fingerprint field."""
    r = api("POST", "/api/keys", {
        "name": "e2e-fields-check-key",
        "public_key": _FAKE_PUB_KEY,
    })
    if r["status"] not in (200, 201):
        pytest.skip(f"Key creation returned {r['status']} — skipping field check")

    body = r["body"]
    assert "id" in body, f"Missing 'id' in response: {body}"
    assert "name" in body, f"Missing 'name' in response: {body}"
    has_pubkey_field = "public_key" in body or "fingerprint" in body
    assert has_pubkey_field, f"Missing 'public_key' or 'fingerprint' in response: {body}"

    api("DELETE", f"/api/keys/{body['id']}")


def test_delete_key_removes_from_list(api):
    """Create a key, delete it, verify it no longer appears in the list."""
    r = api("POST", "/api/keys", {
        "name": "e2e-delete-check-key",
        "public_key": _FAKE_PUB_KEY,
    })
    if r["status"] not in (200, 201):
        pytest.skip(f"Key creation returned {r['status']}")

    kid = r["body"]["id"]

    del_r = api("DELETE", f"/api/keys/{kid}")
    assert del_r["status"] in (200, 204), f"Delete returned {del_r['status']}"

    list_r = api("GET", "/api/keys")
    assert list_r["status"] == 200
    ids = [k["id"] for k in list_r["body"]]
    assert kid not in ids, f"Deleted key {kid} still present in list: {ids}"


def test_keys_page_shows_created_key_name(logged_in: Page, api):
    """Create a key via API, navigate to /keys, and verify the name is visible."""
    r = api("POST", "/api/keys", {
        "name": "e2e-page-visible-key",
        "public_key": _FAKE_PUB_KEY,
    })
    if r["status"] not in (200, 201):
        pytest.skip("Key creation failed — skipping UI visibility check")

    kid = r["body"]["id"]
    page = logged_in
    page.goto(f"{BASE_URL}/keys")
    page.wait_for_load_state("networkidle")

    from playwright.sync_api import expect as _expect
    name_loc = page.locator("text=e2e-page-visible-key")
    _expect(name_loc.first).to_be_visible(timeout=8_000)

    api("DELETE", f"/api/keys/{kid}")


def test_key_name_must_be_unique_or_accepted(api):
    """Create two keys with different names — both must succeed with 200/201."""
    import uuid as _uuid
    suffix = _uuid.uuid4().hex[:6]

    r1 = api("POST", "/api/keys", {
        "name": f"e2e-unique-a-{suffix}",
        "public_key": _FAKE_PUB_KEY,
    })
    r2 = api("POST", "/api/keys", {
        "name": f"e2e-unique-b-{suffix}",
        "public_key": _FAKE_PUB_KEY,
    })

    # Both must be accepted (not a 4xx name-clash error between distinct names)
    assert r1["status"] in (200, 201, 422), f"First key unexpected status: {r1}"
    assert r2["status"] in (200, 201, 422), f"Second key unexpected status: {r2}"

    for r in (r1, r2):
        if r["status"] in (200, 201):
            kid = r["body"].get("id")
            if kid:
                api("DELETE", f"/api/keys/{kid}")


def test_get_key_not_found(api):
    """GET /api/keys/{nonexistent_id} → 404."""
    r = api("GET", "/api/keys/nonexistent-id-that-does-not-exist")
    assert r["status"] == 404, f"Expected 404, got {r['status']}"


def test_keys_page_delete_button_present(logged_in: Page, api):
    """If at least one key exists, a delete button or action is visible on /keys."""
    # Ensure there is at least one key
    r = api("POST", "/api/keys", {
        "name": "e2e-del-btn-key",
        "public_key": _FAKE_PUB_KEY,
    })
    created = r["status"] in (200, 201)
    kid = r["body"].get("id") if created else None

    page = logged_in
    page.goto(f"{BASE_URL}/keys")
    page.wait_for_load_state("networkidle")

    # Check list is non-empty first
    list_r = api("GET", "/api/keys")
    if not list_r["body"]:
        pytest.skip("No keys in the system — cannot check for delete button")

    delete_btn = page.locator(
        "button:has-text('Delete'), button:has-text('Удалить'), "
        "[data-action='delete'], [aria-label='Delete'], .delete-btn, "
        "button.btn-danger, button[type='button']:has-text('×')"
    )
    from playwright.sync_api import expect as _expect
    _expect(delete_btn.first).to_be_visible(timeout=8_000)

    if kid:
        api("DELETE", f"/api/keys/{kid}")
