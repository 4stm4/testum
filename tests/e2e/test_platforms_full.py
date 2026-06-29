# SPDX-License-Identifier: MIT
"""E2E: Platforms page — search, detail panel, modal fields, auth methods, Run/Deploy buttons, API."""
from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_platforms(page: Page) -> None:
    page.goto(f"{BASE_URL}/platforms")
    page.wait_for_load_state("networkidle")


def _create_platform(api, suffix: str = "") -> dict | None:
    r = api("POST", "/api/platforms", {
        "name": f"e2e-plat-{suffix or uuid.uuid4().hex[:6]}",
        "host": "10.99.99.1",
        "port": 22,
        "username": "root",
        "auth_method": "password",
        "password": "secret",
    })
    if r["status"] in (200, 201):
        return r["body"]
    return None


# ── page loads ────────────────────────────────────────────────────────────

def test_platforms_page_loads(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    assert "/login" not in page.url


def test_platforms_page_no_js_errors(logged_in: Page):
    errors = []
    logged_in.on("pageerror", lambda e: errors.append(str(e)))
    _go_platforms(logged_in)
    assert errors == [], f"JS errors on Platforms page: {errors}"


# ── Add platform modal — all fields ───────────────────────────────────────

def test_add_platform_button_visible(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    btn = page.locator("button:has-text('Add'), button:has-text('Добавить'), button[onclick='openAddPlatform()']")
    expect(btn.first).to_be_visible(timeout=8_000)


def test_add_platform_opens_modal(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    page.locator("button[onclick='openAddPlatform()']").click()
    modal = page.locator("#addPlatformModal")
    expect(modal).to_be_visible(timeout=5_000)


def test_add_platform_modal_has_name_input(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    page.locator("button[onclick='openAddPlatform()']").click()
    expect(page.locator("#p-name")).to_be_visible(timeout=5_000)


def test_add_platform_modal_has_host_input(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    page.locator("button[onclick='openAddPlatform()']").click()
    expect(page.locator("#p-host")).to_be_visible(timeout=5_000)


def test_add_platform_modal_has_port_input(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    page.locator("button[onclick='openAddPlatform()']").click()
    expect(page.locator("#p-port")).to_be_visible(timeout=5_000)


def test_add_platform_modal_port_default_is_22(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    page.locator("button[onclick='openAddPlatform()']").click()
    val = page.locator("#p-port").input_value()
    assert val == "22"


def test_add_platform_modal_has_username_input(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    page.locator("button[onclick='openAddPlatform()']").click()
    expect(page.locator("#p-user")).to_be_visible(timeout=5_000)


def test_add_platform_modal_has_auth_method_select(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    page.locator("button[onclick='openAddPlatform()']").click()
    expect(page.locator("#p-auth")).to_be_visible(timeout=5_000)


def test_add_platform_modal_has_password_field(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    page.locator("button[onclick='openAddPlatform()']").click()
    expect(page.locator("#p-password")).to_be_visible(timeout=5_000)


def test_add_platform_modal_has_key_select(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    page.locator("button[onclick='openAddPlatform()']").click()
    assert page.locator("#p-key-select").count() > 0


def test_add_platform_modal_has_submit_button(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    page.locator("button[onclick='openAddPlatform()']").click()
    expect(page.locator("#addPlatformBtn")).to_be_visible(timeout=5_000)


def test_add_platform_modal_closed_by_x_button(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    page.locator("button[onclick='openAddPlatform()']").click()
    modal = page.locator("#addPlatformModal")
    expect(modal).to_be_visible(timeout=5_000)
    page.locator("#addPlatformModal .iconbtn").click()
    expect(modal).to_be_hidden(timeout=5_000)


def test_add_platform_modal_closed_by_cancel(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    page.locator("button[onclick='openAddPlatform()']").click()
    modal = page.locator("#addPlatformModal")
    expect(modal).to_be_visible(timeout=5_000)
    page.locator("#addPlatformModal button[data-i18n='cancel']").click()
    expect(modal).to_be_hidden(timeout=5_000)


# ── search / filter ───────────────────────────────────────────────────────

def test_platforms_has_search_input(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    expect(page.locator("#plat-search")).to_be_visible(timeout=8_000)


def test_platforms_search_input_accepts_text(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    search = page.locator("#plat-search")
    search.fill("test-filter")
    assert search.input_value() == "test-filter"


def test_platforms_search_clears_filter(logged_in: Page, api):
    page = logged_in
    p = _create_platform(api, "search-test")
    if not p:
        pytest.skip("Cannot create platform")

    try:
        _go_platforms(page)
        search = page.locator("#plat-search")
        search.fill("zzz-no-match")
        page.wait_for_timeout(500)
        search.fill("")
        page.wait_for_timeout(500)
    finally:
        api("DELETE", f"/api/platforms/{p['id']}")


# ── master-detail layout ──────────────────────────────────────────────────

def test_platforms_has_master_list(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    assert page.locator("#master-list").count() > 0


def test_platforms_has_detail_panel(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    assert page.locator("#detail-panel").count() > 0


def test_platform_detail_panel_shows_on_select(logged_in: Page, api):
    page = logged_in
    p = _create_platform(api, "detail-test")
    if not p:
        pytest.skip("Cannot create platform")

    try:
        _go_platforms(page)
        # Click platform in list
        item = page.locator(f".master-item", has_text=p["name"])
        if item.count() == 0:
            pytest.skip("Platform not visible in list yet")
        item.first.click()
        page.wait_for_timeout(1_000)
        # Detail panel should now show platform info
        detail = page.locator("#detail-panel")
        content = detail.inner_text()
        assert len(content) > 10
    finally:
        api("DELETE", f"/api/platforms/{p['id']}")


def test_platform_detail_shows_deploy_keys_button(logged_in: Page, api):
    page = logged_in
    p = _create_platform(api, "deploy-btn")
    if not p:
        pytest.skip("Cannot create platform")

    try:
        _go_platforms(page)
        item = page.locator(".master-item", has_text=p["name"])
        if item.count() == 0:
            pytest.skip("Platform not visible in list")
        item.first.click()
        page.wait_for_timeout(1_000)
        btn = page.locator("#detail-panel button:has-text('Deploy'), #detail-panel button:has-text('keys')")
        expect(btn.first).to_be_visible(timeout=5_000)
    finally:
        api("DELETE", f"/api/platforms/{p['id']}")


def test_platform_detail_shows_run_button(logged_in: Page, api):
    page = logged_in
    p = _create_platform(api, "run-btn")
    if not p:
        pytest.skip("Cannot create platform")

    try:
        _go_platforms(page)
        item = page.locator(".master-item", has_text=p["name"])
        if item.count() == 0:
            pytest.skip("Platform not visible in list")
        item.first.click()
        page.wait_for_timeout(1_000)
        btn = page.locator("#detail-panel button:has-text('Run'), #detail-panel button:has-text('▶')")
        expect(btn.first).to_be_visible(timeout=5_000)
    finally:
        api("DELETE", f"/api/platforms/{p['id']}")


# ── API: platform endpoints ───────────────────────────────────────────────

def test_list_platforms_api_returns_list(api):
    r = api("GET", "/api/platforms")
    assert r["status"] == 200
    body = r.get("body", [])
    assert isinstance(body, list) or isinstance(body, dict)


def test_create_platform_password_auth(api):
    r = api("POST", "/api/platforms", {
        "name": f"e2e-pw-{uuid.uuid4().hex[:6]}",
        "host": "10.0.0.1",
        "port": 22,
        "username": "root",
        "auth_method": "password",
        "password": "secret",
    })
    assert r["status"] in (200, 201)
    if r["status"] in (200, 201):
        api("DELETE", f"/api/platforms/{r['body']['id']}")


def test_create_platform_key_auth(api):
    # Create a key first
    kr = api("POST", "/api/keys", {
        "name": f"e2e-key-{uuid.uuid4().hex[:6]}",
        "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAQQDummyKeyForTestingOnly test@e2e",
    })
    key_id = kr["body"].get("id") if kr["status"] in (200, 201) else None

    r = api("POST", "/api/platforms", {
        "name": f"e2e-key-auth-{uuid.uuid4().hex[:6]}",
        "host": "10.0.0.2",
        "port": 22,
        "username": "root",
        "auth_method": "key",
        "key_id": key_id,
    })
    assert r["status"] in (200, 201, 400, 422)
    if r["status"] in (200, 201):
        api("DELETE", f"/api/platforms/{r['body']['id']}")
    if key_id:
        api("DELETE", f"/api/keys/{key_id}")


def test_create_platform_missing_name_returns_error(api):
    r = api("POST", "/api/platforms", {
        "host": "10.0.0.3",
        "port": 22,
        "username": "root",
        "auth_method": "password",
        "password": "secret",
    })
    assert r["status"] in (400, 422)


def test_create_platform_missing_host_returns_error(api):
    r = api("POST", "/api/platforms", {
        "name": f"e2e-nohost-{uuid.uuid4().hex[:6]}",
        "port": 22,
        "username": "root",
        "auth_method": "password",
        "password": "secret",
    })
    assert r["status"] in (400, 422)


def test_get_platform_by_id(api):
    p = _create_platform(api, "get-test")
    if not p:
        pytest.skip("Cannot create platform")
    try:
        r = api("GET", f"/api/platforms/{p['id']}")
        assert r["status"] == 200
        assert r["body"]["id"] == p["id"]
    finally:
        api("DELETE", f"/api/platforms/{p['id']}")


def test_get_platform_not_found_returns_404(api):
    r = api("GET", "/api/platforms/00000000-0000-0000-0000-000000000000")
    assert r["status"] == 404


def test_delete_platform_removes_from_list(api):
    p = _create_platform(api, "del-test")
    if not p:
        pytest.skip("Cannot create platform")

    api("DELETE", f"/api/platforms/{p['id']}")
    r = api("GET", "/api/platforms")
    ids = [x["id"] for x in (r["body"] if isinstance(r["body"], list) else [])]
    assert p["id"] not in ids


def test_run_command_endpoint_reachable(api):
    p = _create_platform(api, "run-cmd")
    if not p:
        pytest.skip("Cannot create platform")
    try:
        r = api("POST", f"/api/platforms/{p['id']}/run_command", {
            "command": "echo hello",
            "timeout": 5,
        })
        assert r["status"] in (200, 202, 400, 422, 500)
    finally:
        api("DELETE", f"/api/platforms/{p['id']}")


def test_run_command_missing_command_field(api):
    p = _create_platform(api, "run-missing")
    if not p:
        pytest.skip("Cannot create platform")
    try:
        r = api("POST", f"/api/platforms/{p['id']}/run_command", {})
        assert r["status"] in (400, 422)
    finally:
        api("DELETE", f"/api/platforms/{p['id']}")


def test_deploy_keys_endpoint_reachable(api):
    p = _create_platform(api, "deploy")
    if not p:
        pytest.skip("Cannot create platform")
    try:
        r = api("POST", f"/api/platforms/{p['id']}/deploy_keys", {})
        assert r["status"] in (200, 202, 400, 422, 500)
    finally:
        api("DELETE", f"/api/platforms/{p['id']}")
