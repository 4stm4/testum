# SPDX-License-Identifier: MIT
"""E2E: Storage pools page — all buttons, modals, form fields, API endpoints."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_pools(page: Page) -> None:
    page.goto(f"{BASE_URL}/virt/pools")
    page.wait_for_load_state("networkidle")


def _get_or_create_platform(api) -> str | None:
    r = api("GET", "/api/platforms")
    body = r.get("body", [])
    items = body if isinstance(body, list) else body.get("items", [])
    if items:
        return items[0]["id"]
    r2 = api("POST", "/api/platforms", {
        "name": "e2e-pool-host",
        "host": "127.0.0.1",
        "port": 22,
        "username": "root",
        "auth_method": "password",
        "password": "secret",
    })
    if r2["status"] in (200, 201):
        return r2["body"]["id"]
    return None


# ── page loads ────────────────────────────────────────────────────────────

def test_virt_pools_page_loads(logged_in: Page):
    page = logged_in
    _go_pools(page)
    assert "/login" not in page.url
    assert "/virt/pools" in page.url


def test_virt_pools_page_has_main_content(logged_in: Page):
    page = logged_in
    _go_pools(page)
    assert len(page.locator("main").inner_text()) > 0


def test_virt_pools_page_no_js_errors(logged_in: Page):
    errors = []
    logged_in.on("pageerror", lambda e: errors.append(str(e)))
    _go_pools(logged_in)
    assert errors == [], f"JS errors on Pools page: {errors}"


# ── header buttons ────────────────────────────────────────────────────────

def test_virt_pools_has_refresh_button(logged_in: Page):
    page = logged_in
    _go_pools(page)
    btn = page.locator("#refreshBtn")
    expect(btn).to_be_visible(timeout=8_000)


def test_virt_pools_has_add_pool_button(logged_in: Page):
    page = logged_in
    _go_pools(page)
    btn = page.locator("#addPoolBtn")
    expect(btn).to_be_visible(timeout=8_000)


def test_virt_pools_platform_select_exists(logged_in: Page):
    page = logged_in
    _go_pools(page)
    assert page.locator("#platformSelect").count() > 0


# ── pools table ───────────────────────────────────────────────────────────

def test_virt_pools_table_exists(logged_in: Page):
    page = logged_in
    _go_pools(page)
    tbody = page.locator("#poolsBody")
    assert tbody.count() > 0


def test_virt_pools_table_placeholder_shown(logged_in: Page):
    page = logged_in
    _go_pools(page)
    content = page.locator("#poolsBody").inner_text()
    assert len(content) > 0


# ── Add Pool modal ────────────────────────────────────────────────────────

def test_add_pool_button_opens_modal(logged_in: Page):
    page = logged_in
    _go_pools(page)
    page.locator("#addPoolBtn").click()
    modal = page.locator("#addPoolModal")
    expect(modal).to_be_visible(timeout=5_000)


def test_add_pool_modal_has_platform_select(logged_in: Page):
    page = logged_in
    _go_pools(page)
    page.locator("#addPoolBtn").click()
    expect(page.locator("#modalPlatformSelect")).to_be_visible(timeout=5_000)


def test_add_pool_modal_has_name_input(logged_in: Page):
    page = logged_in
    _go_pools(page)
    page.locator("#addPoolBtn").click()
    expect(page.locator("#poolName")).to_be_visible(timeout=5_000)


def test_add_pool_modal_has_type_select(logged_in: Page):
    page = logged_in
    _go_pools(page)
    page.locator("#addPoolBtn").click()
    expect(page.locator("#poolType")).to_be_visible(timeout=5_000)


def test_add_pool_modal_has_source_input(logged_in: Page):
    page = logged_in
    _go_pools(page)
    page.locator("#addPoolBtn").click()
    expect(page.locator("#poolSource")).to_be_visible(timeout=5_000)


def test_add_pool_modal_has_target_input(logged_in: Page):
    page = logged_in
    _go_pools(page)
    page.locator("#addPoolBtn").click()
    expect(page.locator("#poolTarget")).to_be_visible(timeout=5_000)


def test_add_pool_modal_has_host_input(logged_in: Page):
    page = logged_in
    _go_pools(page)
    page.locator("#addPoolBtn").click()
    expect(page.locator("#poolHost")).to_be_visible(timeout=5_000)


def test_add_pool_modal_has_create_button(logged_in: Page):
    page = logged_in
    _go_pools(page)
    page.locator("#addPoolBtn").click()
    expect(page.locator("#createPoolBtn")).to_be_visible(timeout=5_000)


def test_add_pool_modal_closed_by_x_button(logged_in: Page):
    page = logged_in
    _go_pools(page)
    page.locator("#addPoolBtn").click()
    modal = page.locator("#addPoolModal")
    expect(modal).to_be_visible(timeout=5_000)
    page.locator("#addPoolModal .iconbtn").click()
    expect(modal).to_be_hidden(timeout=5_000)


def test_add_pool_modal_closed_by_cancel_button(logged_in: Page):
    page = logged_in
    _go_pools(page)
    page.locator("#addPoolBtn").click()
    modal = page.locator("#addPoolModal")
    expect(modal).to_be_visible(timeout=5_000)
    page.locator("#addPoolModal button[data-i18n='cancel']").click()
    expect(modal).to_be_hidden(timeout=5_000)


# ── Delete Pool modal ─────────────────────────────────────────────────────

def test_delete_pool_modal_exists_in_dom(logged_in: Page):
    page = logged_in
    _go_pools(page)
    assert page.locator("#deleteModal").count() > 0


def test_delete_pool_modal_has_confirm_button(logged_in: Page):
    page = logged_in
    _go_pools(page)
    assert page.locator("#confirmDeleteBtn").count() > 0


# ── API: pool endpoints ───────────────────────────────────────────────────

def test_list_pools_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("GET", f"/api/virt/{pid}/pools")
    assert r["status"] in (200, 500)


def test_create_pool_api_accepts_valid_schema(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/pools/create", {
        "name": "e2e-pool",
        "pool_type": "dir",
        "target_path": "/var/lib/libvirt/images",
    })
    assert r["status"] != 422, "Pool create API rejected valid schema"


def test_create_pool_api_missing_name_returns_error(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/pools/create", {
        "pool_type": "dir",
        "target_path": "/var/lib/libvirt/images",
    })
    assert r["status"] in (400, 422, 500)


def test_activate_pool_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/pools/activate", {"name": "e2e-nonexistent"})
    assert r["status"] in (200, 400, 422, 500)


def test_deactivate_pool_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/pools/deactivate", {"name": "e2e-nonexistent"})
    assert r["status"] in (200, 400, 422, 500)


def test_delete_pool_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/pools/delete", {"name": "e2e-nonexistent"})
    assert r["status"] in (200, 404, 400, 422, 500)


def test_pool_usage_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("GET", f"/api/virt/{pid}/pools/usage")
    assert r["status"] in (200, 500)


def test_pool_endpoint_unknown_platform_returns_error(api):
    r = api("GET", "/api/virt/00000000-0000-0000-0000-000000000000/pools")
    assert r["status"] in (404, 400, 500)
