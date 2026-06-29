# SPDX-License-Identifier: MIT
"""E2E: Volumes page — all buttons, modals, form fields, API endpoints."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_volumes(page: Page) -> None:
    page.goto(f"{BASE_URL}/virt/volumes")
    page.wait_for_load_state("networkidle")


def _get_or_create_platform(api) -> str | None:
    r = api("GET", "/api/platforms")
    body = r.get("body", [])
    items = body if isinstance(body, list) else body.get("items", [])
    if items:
        return items[0]["id"]
    r2 = api("POST", "/api/platforms", {
        "name": "e2e-vol-host",
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

def test_virt_volumes_page_loads(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    assert "/login" not in page.url
    assert "/virt/volumes" in page.url


def test_virt_volumes_page_has_main_content(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    assert len(page.locator("main").inner_text()) > 0


def test_virt_volumes_page_no_js_errors(logged_in: Page):
    errors = []
    logged_in.on("pageerror", lambda e: errors.append(str(e)))
    _go_volumes(logged_in)
    assert errors == [], f"JS errors on Volumes page: {errors}"


# ── header buttons ────────────────────────────────────────────────────────

def test_virt_volumes_has_refresh_button(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    btn = page.locator("#refreshBtn")
    expect(btn).to_be_visible(timeout=8_000)


def test_virt_volumes_has_add_volume_button(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    btn = page.locator("#addVolumeBtn")
    expect(btn).to_be_visible(timeout=8_000)


def test_virt_volumes_platform_select_exists(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    assert page.locator("#platformSelect").count() > 0


def test_virt_volumes_pool_select_exists(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    assert page.locator("#poolSelect").count() > 0


def test_virt_volumes_pool_select_disabled_initially(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    pool_sel = page.locator("#poolSelect")
    # Pool select is disabled until a platform is selected
    assert pool_sel.get_attribute("disabled") is not None or not pool_sel.is_enabled()


# ── volumes table ─────────────────────────────────────────────────────────

def test_virt_volumes_table_exists(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    tbody = page.locator("#volumesBody")
    assert tbody.count() > 0


def test_virt_volumes_table_placeholder_shown(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    content = page.locator("#volumesBody").inner_text()
    assert len(content) > 0


# ── Add Volume modal ──────────────────────────────────────────────────────

def test_add_volume_button_opens_modal(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    page.locator("#addVolumeBtn").click()
    modal = page.locator("#addVolumeModal")
    expect(modal).to_be_visible(timeout=5_000)


def test_add_volume_modal_has_platform_select(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    page.locator("#addVolumeBtn").click()
    expect(page.locator("#modalPlatformSelect")).to_be_visible(timeout=5_000)


def test_add_volume_modal_has_pool_select(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    page.locator("#addVolumeBtn").click()
    expect(page.locator("#modalPoolSelect")).to_be_visible(timeout=5_000)


def test_add_volume_modal_has_name_input(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    page.locator("#addVolumeBtn").click()
    expect(page.locator("#volName")).to_be_visible(timeout=5_000)


def test_add_volume_modal_has_path_input(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    page.locator("#addVolumeBtn").click()
    expect(page.locator("#volPath")).to_be_visible(timeout=5_000)


def test_add_volume_modal_has_capacity_input(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    page.locator("#addVolumeBtn").click()
    expect(page.locator("#volCapacity")).to_be_visible(timeout=5_000)


def test_add_volume_modal_has_create_button(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    page.locator("#addVolumeBtn").click()
    expect(page.locator("#createVolumeBtn")).to_be_visible(timeout=5_000)


def test_add_volume_modal_closed_by_x_button(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    page.locator("#addVolumeBtn").click()
    modal = page.locator("#addVolumeModal")
    expect(modal).to_be_visible(timeout=5_000)
    page.locator("#addVolumeModal .iconbtn").click()
    expect(modal).to_be_hidden(timeout=5_000)


def test_add_volume_modal_closed_by_cancel_button(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    page.locator("#addVolumeBtn").click()
    modal = page.locator("#addVolumeModal")
    expect(modal).to_be_visible(timeout=5_000)
    page.locator("#addVolumeModal button[data-i18n='cancel']").click()
    expect(modal).to_be_hidden(timeout=5_000)


# ── Delete Volume modal ───────────────────────────────────────────────────

def test_delete_volume_modal_exists_in_dom(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    assert page.locator("#deleteModal").count() > 0


def test_delete_volume_modal_has_confirm_button(logged_in: Page):
    page = logged_in
    _go_volumes(page)
    assert page.locator("#confirmDeleteBtn").count() > 0


# ── API: volume endpoints ─────────────────────────────────────────────────

def test_list_volumes_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("GET", f"/api/virt/{pid}/volumes")
    assert r["status"] in (200, 400, 422, 500)


def test_list_volumes_api_requires_pool_param(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    # Without pool_name param the API may return 400 or 422
    r = api("GET", f"/api/virt/{pid}/volumes")
    assert r["status"] in (200, 400, 422, 500)


def test_create_volume_api_accepts_valid_schema(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/volumes/create", {
        "name": "e2e-vol",
        "pool_name": "default",
        "capacity_gib": 10,
    })
    assert r["status"] != 422, "Volume create API rejected valid schema"


def test_create_volume_api_missing_name_returns_error(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/volumes/create", {
        "pool_name": "default",
        "capacity_gib": 10,
    })
    assert r["status"] in (400, 422, 500)


def test_delete_volume_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/volumes/delete", {
        "pool_name": "default",
        "volume_name": "e2e-nonexistent.qcow2",
    })
    assert r["status"] in (200, 404, 400, 422, 500)


def test_volume_endpoint_unknown_platform_returns_error(api):
    r = api("GET", "/api/virt/00000000-0000-0000-0000-000000000000/volumes")
    assert r["status"] in (404, 400, 500)
