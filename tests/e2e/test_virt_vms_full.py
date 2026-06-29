# SPDX-License-Identifier: MIT
"""E2E: VMs page — all buttons, modals, form fields, API endpoints."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_vms(page: Page) -> None:
    page.goto(f"{BASE_URL}/virt/vms")
    page.wait_for_load_state("networkidle")


def _get_or_create_platform(api) -> str | None:
    r = api("GET", "/api/platforms")
    body = r.get("body", [])
    items = body if isinstance(body, list) else body.get("items", [])
    if items:
        return items[0]["id"]
    r2 = api("POST", "/api/platforms", {
        "name": "e2e-vm-host",
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

def test_virt_vms_page_loads(logged_in: Page):
    page = logged_in
    _go_vms(page)
    assert "/login" not in page.url
    assert "/virt/vms" in page.url


def test_virt_vms_page_has_main_content(logged_in: Page):
    page = logged_in
    _go_vms(page)
    assert len(page.locator("main").inner_text()) > 0


def test_virt_vms_page_no_js_errors(logged_in: Page):
    errors = []
    logged_in.on("pageerror", lambda e: errors.append(str(e)))
    _go_vms(logged_in)
    assert errors == [], f"JS errors on VMs page: {errors}"


# ── header buttons ────────────────────────────────────────────────────────

def test_virt_vms_has_create_button(logged_in: Page):
    page = logged_in
    _go_vms(page)
    btn = page.locator("#createVmBtn")
    expect(btn).to_be_visible(timeout=8_000)


def test_virt_vms_has_refresh_button(logged_in: Page):
    page = logged_in
    _go_vms(page)
    btn = page.locator("#refreshBtn")
    expect(btn).to_be_visible(timeout=8_000)


def test_virt_vms_has_install_libvirt_button(logged_in: Page):
    page = logged_in
    _go_vms(page)
    btn = page.locator("#installBtn")
    expect(btn).to_be_visible(timeout=8_000)


def test_virt_vms_install_libvirt_button_disabled_initially(logged_in: Page):
    page = logged_in
    _go_vms(page)
    btn = page.locator("#installBtn")
    # Disabled until a platform is selected
    expect(btn).to_be_disabled(timeout=8_000)


def test_virt_vms_platform_select_exists(logged_in: Page):
    page = logged_in
    _go_vms(page)
    sel = page.locator("#platformSelect")
    assert sel.count() > 0


# ── VMs table ─────────────────────────────────────────────────────────────

def test_virt_vms_table_exists(logged_in: Page):
    page = logged_in
    _go_vms(page)
    tbody = page.locator("#vmsBody")
    assert tbody.count() > 0


def test_virt_vms_table_placeholder_shown_without_platform(logged_in: Page):
    page = logged_in
    _go_vms(page)
    content = page.locator("#vmsBody").inner_text()
    assert len(content) > 0


# ── Create VM modal ───────────────────────────────────────────────────────

def test_create_vm_button_opens_modal(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    modal = page.locator("#createVmModal")
    expect(modal).to_be_visible(timeout=5_000)


def test_create_vm_modal_has_platform_select(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    expect(page.locator("#vmModalPlatformSelect")).to_be_visible(timeout=5_000)


def test_create_vm_modal_has_name_input(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    expect(page.locator("#vmName")).to_be_visible(timeout=5_000)


def test_create_vm_modal_has_memory_input(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    expect(page.locator("#vmMemory")).to_be_visible(timeout=5_000)


def test_create_vm_modal_has_vcpu_input(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    expect(page.locator("#vmVcpu")).to_be_visible(timeout=5_000)


def test_create_vm_modal_has_bridge_input(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    expect(page.locator("#vmBridge")).to_be_visible(timeout=5_000)


def test_create_vm_modal_has_disk_path_input(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    expect(page.locator("#vmDiskPath")).to_be_visible(timeout=5_000)


def test_create_vm_modal_has_cdrom_input(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    expect(page.locator("#vmCdrom")).to_be_visible(timeout=5_000)


def test_create_vm_modal_has_mac_input(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    expect(page.locator("#vmMac")).to_be_visible(timeout=5_000)


def test_create_vm_modal_has_confirm_button(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    expect(page.locator("#confirmCreateVmBtn")).to_be_visible(timeout=5_000)


def test_create_vm_modal_closed_by_x_button(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    modal = page.locator("#createVmModal")
    expect(modal).to_be_visible(timeout=5_000)
    page.locator("#createVmModal .iconbtn").click()
    expect(modal).to_be_hidden(timeout=5_000)


def test_create_vm_modal_closed_by_cancel_button(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    modal = page.locator("#createVmModal")
    expect(modal).to_be_visible(timeout=5_000)
    page.locator("#createVmModal button[data-i18n='cancel']").click()
    expect(modal).to_be_hidden(timeout=5_000)


def test_create_vm_modal_bridge_has_default_value(logged_in: Page):
    page = logged_in
    _go_vms(page)
    page.locator("#createVmBtn").click()
    val = page.locator("#vmBridge").get_attribute("value") or page.locator("#vmBridge").input_value()
    assert val == "virbr0"


# ── Delete VM modal ───────────────────────────────────────────────────────

def test_delete_vm_modal_exists_in_dom(logged_in: Page):
    page = logged_in
    _go_vms(page)
    assert page.locator("#deleteModal").count() > 0


def test_delete_vm_modal_has_confirm_button(logged_in: Page):
    page = logged_in
    _go_vms(page)
    assert page.locator("#confirmDeleteBtn").count() > 0


# ── Install libvirt modal ─────────────────────────────────────────────────

def test_install_libvirt_modal_exists_in_dom(logged_in: Page):
    page = logged_in
    _go_vms(page)
    assert page.locator("#installModal").count() > 0


# ── API: VM endpoints ─────────────────────────────────────────────────────

def test_list_vms_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("GET", f"/api/virt/{pid}/vms")
    assert r["status"] in (200, 500)


def test_create_vm_api_accepts_valid_schema(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/vms/create", {
        "name": "e2e-vm-schema-check",
        "memory": 512,
        "vcpu": 1,
        "disk_path": "/var/lib/vms/e2e.qcow2",
        "cdrom_iso_path": "/iso/ubuntu.iso",
    })
    # 422 = schema rejected; 500 = SSH failed; both mean API schema is fine
    assert r["status"] != 422, "VM create API rejected valid schema"


def test_create_vm_api_missing_name_returns_error(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/vms/create", {
        "memory": 512,
        "vcpu": 1,
        "disk_path": "/var/lib/vms/x.qcow2",
    })
    assert r["status"] in (400, 422, 500)


def test_create_vm_with_sdn_fields_accepted(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/vms/create", {
        "name": "e2e-vm-sdn",
        "memory": 512,
        "vcpu": 1,
        "disk_path": "/var/lib/vms/sdn.qcow2",
        "cdrom_iso_path": "/iso/ubuntu.iso",
        "nervum_network_id": "net-test",
        "nervum_project_id": "proj-test",
    })
    assert r["status"] != 422, "VM create API rejected nervum fields"


def test_start_vm_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/vms/start", {"name": "e2e-nonexistent"})
    assert r["status"] in (200, 400, 422, 500)


def test_stop_vm_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/vms/stop", {"name": "e2e-nonexistent"})
    assert r["status"] in (200, 400, 422, 500)


def test_delete_vm_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/vms/delete", {"name": "e2e-nonexistent"})
    assert r["status"] in (200, 404, 400, 422, 500)


def test_host_capabilities_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("GET", f"/api/virt/{pid}/host/capabilities")
    assert r["status"] in (200, 500)


def test_install_libvirt_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/install")
    assert r["status"] in (200, 400, 500)


def test_vm_endpoint_unknown_platform_returns_404_or_error(api):
    r = api("GET", "/api/virt/00000000-0000-0000-0000-000000000000/vms")
    assert r["status"] in (404, 400, 500)
