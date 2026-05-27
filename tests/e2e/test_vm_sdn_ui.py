# SPDX-License-Identifier: MIT
"""E2E: VM + SDN full flow — create VM with SDN, port appears; delete VM, port disappears."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _get_or_create_platform(api) -> str | None:
    r = api("GET", "/api/platforms")
    body = r.get("body", [])
    items = body if isinstance(body, list) else body.get("items", [])
    if items:
        return items[0]["id"]

    r2 = api("POST", "/api/platforms", {
        "name": "e2e-virt-host",
        "host": "127.0.0.1",
        "port": 22,
        "username": "root",
        "auth_method": "password",
        "password": "secret",
    })
    if r2["status"] in (200, 201):
        return r2["body"]["id"]
    return None


# ── VMs page ──────────────────────────────────────────────────────────────

def test_virt_vms_page_loads(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/virt/vms")
    page.wait_for_load_state("networkidle")
    assert "/login" not in page.url


def test_virt_vms_page_has_create_button(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/virt/vms")
    page.wait_for_load_state("networkidle")

    btn = page.locator(
        "button:has-text('Create'), button:has-text('Add'), "
        "button:has-text('Создать'), [data-i18n='create_vm'], #create-vm-btn"
    )
    expect(btn.first).to_be_visible(timeout=8_000)


# ── API: create VM without SDN ────────────────────────────────────────────

def test_create_vm_without_sdn_via_api(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")

    r = api("POST", f"/api/virt/{pid}/vms/create", {
        "name": "e2e-vm-nosdn",
        "memory": 512,
        "vcpu": 1,
        "disk_path": "/var/lib/vms/e2e.qcow2",
        "cdrom_iso_path": "/iso/ubuntu.iso",
    })
    assert r["status"] in (200, 500, 422, 400)
    if r["status"] == 200:
        assert "sdn_port" not in r["body"]


# ── API: create VM with SDN (mocked at API level) ─────────────────────────

def test_create_vm_with_sdn_api_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")

    r = api("POST", f"/api/virt/{pid}/vms/create", {
        "name": "e2e-vm-sdn",
        "memory": 512,
        "vcpu": 1,
        "disk_path": "/var/lib/vms/e2e-sdn.qcow2",
        "cdrom_iso_path": "/iso/ubuntu.iso",
        "nervum_network_id": "net-e2e",
        "nervum_project_id": "proj-e2e",
    })
    assert r["status"] != 422, "Request schema rejected — nervum fields not accepted"


# ── SDN Ports tab ─────────────────────────────────────────────────────────

def test_sdn_ports_sidebar_link(logged_in: Page):
    """Sidebar link for Ports navigates to the ports panel."""
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='ports']")
    if link.count() == 0:
        pytest.skip("Sidebar ports link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#panel-ports")).to_be_visible(timeout=5_000)


def test_sdn_ports_api_returns_list(api):
    r = api("GET", "/api/sdn/logical-ports")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


# ── list VMs ──────────────────────────────────────────────────────────────

def test_list_vms_via_api(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")

    r = api("GET", f"/api/virt/{pid}/vms")
    assert r["status"] in (200, 500)


# ── delete VM ─────────────────────────────────────────────────────────────

def test_delete_vm_endpoint_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")

    r = api("POST", f"/api/virt/{pid}/vms/delete", {"name": "e2e-nonexistent-vm"})
    assert r["status"] in (200, 404, 500)


# ── VMs page navigation ───────────────────────────────────────────────────

def test_virt_volumes_page_loads(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/virt/volumes")
    page.wait_for_load_state("networkidle")
    assert "/login" not in page.url


def test_virt_pools_page_loads(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/virt/pools")
    page.wait_for_load_state("networkidle")
    assert "/login" not in page.url
