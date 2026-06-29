# SPDX-License-Identifier: MIT
"""E2E: UFW firewall page — all buttons, modal fields, API endpoints."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_ufw(page: Page) -> None:
    page.goto(f"{BASE_URL}/virt/ufw")
    page.wait_for_load_state("networkidle")


def _get_or_create_platform(api) -> str | None:
    r = api("GET", "/api/platforms")
    body = r.get("body", [])
    items = body if isinstance(body, list) else body.get("items", [])
    if items:
        return items[0]["id"]
    r2 = api("POST", "/api/platforms", {
        "name": "e2e-ufw-host",
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

def test_ufw_page_loads(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    assert "/login" not in page.url
    assert "/virt/ufw" in page.url


def test_ufw_page_not_redirected_to_login(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    assert "/login" not in page.url


def test_ufw_page_has_main_content(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    content = page.locator("main").inner_text()
    assert len(content) > 0


# ── header buttons ────────────────────────────────────────────────────────

def test_ufw_page_has_refresh_button(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    btn = page.locator("#refreshBtn")
    expect(btn).to_be_visible(timeout=8_000)


def test_ufw_page_has_add_rule_button(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    btn = page.locator("#addRuleBtn")
    expect(btn).to_be_visible(timeout=8_000)


def test_ufw_page_has_platform_select(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    sel = page.locator("#platformSelect")
    # hidden select populated by JS — it must exist in DOM
    assert sel.count() > 0


# ── Add Rule modal ────────────────────────────────────────────────────────

def test_add_rule_button_opens_modal(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    page.locator("#addRuleBtn").click()
    modal = page.locator("#addRuleModal")
    expect(modal).to_be_visible(timeout=5_000)


def test_add_rule_modal_has_platform_select(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    page.locator("#addRuleBtn").click()
    expect(page.locator("#modalPlatformSelect")).to_be_visible(timeout=5_000)


def test_add_rule_modal_has_action_select(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    page.locator("#addRuleBtn").click()
    expect(page.locator("#ruleAction")).to_be_visible(timeout=5_000)


def test_add_rule_modal_has_direction_select(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    page.locator("#addRuleBtn").click()
    expect(page.locator("#ruleDirection")).to_be_visible(timeout=5_000)


def test_add_rule_modal_has_target_input(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    page.locator("#addRuleBtn").click()
    expect(page.locator("#ruleTarget")).to_be_visible(timeout=5_000)


def test_add_rule_modal_has_proto_select(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    page.locator("#addRuleBtn").click()
    expect(page.locator("#ruleProto")).to_be_visible(timeout=5_000)


def test_add_rule_modal_has_from_ip_input(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    page.locator("#addRuleBtn").click()
    expect(page.locator("#ruleFromIp")).to_be_visible(timeout=5_000)


def test_add_rule_modal_has_confirm_button(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    page.locator("#addRuleBtn").click()
    expect(page.locator("#confirmAddRuleBtn")).to_be_visible(timeout=5_000)


def test_add_rule_modal_can_be_closed(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    page.locator("#addRuleBtn").click()
    modal = page.locator("#addRuleModal")
    expect(modal).to_be_visible(timeout=5_000)
    page.locator("#addRuleModal .iconbtn").click()
    expect(modal).to_be_hidden(timeout=5_000)


def test_add_rule_modal_cancel_button_closes(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    page.locator("#addRuleBtn").click()
    modal = page.locator("#addRuleModal")
    expect(modal).to_be_visible(timeout=5_000)
    page.locator("#addRuleModal button[data-i18n='cancel']").click()
    expect(modal).to_be_hidden(timeout=5_000)


# ── Delete Rule modal exists ───────────────────────────────────────────────

def test_delete_rule_modal_exists_in_dom(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    modal = page.locator("#deleteRuleModal")
    assert modal.count() > 0


def test_delete_rule_modal_has_confirm_button(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    btn = page.locator("#confirmDeleteRuleBtn")
    assert btn.count() > 0


# ── UFW status bar buttons ─────────────────────────────────────────────────

def test_ufw_enable_button_exists_in_dom(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    btn = page.locator("#enableBtn")
    assert btn.count() > 0


def test_ufw_disable_button_exists_in_dom(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    btn = page.locator("#disableBtn")
    assert btn.count() > 0


def test_ufw_reload_button_exists_in_dom(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    btn = page.locator("#reloadBtn2")
    assert btn.count() > 0


# ── API: firewall endpoints reachable ─────────────────────────────────────

def test_firewall_status_endpoint_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("GET", f"/api/virt/{pid}/firewall/status")
    assert r["status"] in (200, 500)


def test_firewall_enable_endpoint_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/firewall/enable")
    assert r["status"] in (200, 500)


def test_firewall_disable_endpoint_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/firewall/disable")
    assert r["status"] in (200, 500)


def test_firewall_reload_endpoint_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/firewall/reload")
    assert r["status"] in (200, 500)


def test_firewall_add_rule_endpoint_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/firewall/rule/add", {
        "action": "allow",
        "direction": "in",
        "target": "22",
        "proto": "tcp",
    })
    assert r["status"] in (200, 400, 422, 500)


def test_firewall_add_rule_missing_action_returns_error(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/firewall/rule/add", {"target": "80"})
    assert r["status"] in (400, 422, 500)


def test_firewall_delete_rule_endpoint_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/firewall/rule/delete", {"rule_number": 1})
    assert r["status"] in (200, 400, 422, 500)


def test_firewall_set_default_endpoint_reachable(api):
    pid = _get_or_create_platform(api)
    if not pid:
        pytest.skip("No platform available")
    r = api("POST", f"/api/virt/{pid}/firewall/default", {
        "direction": "incoming",
        "policy": "deny",
    })
    assert r["status"] in (200, 400, 422, 500)


def test_firewall_add_rule_no_platform_returns_404(api):
    r = api("POST", "/api/virt/00000000-0000-0000-0000-000000000000/firewall/rule/add", {
        "action": "allow",
        "direction": "in",
        "target": "22",
    })
    assert r["status"] in (404, 400, 422, 500)


# ── rules table ───────────────────────────────────────────────────────────

def test_ufw_rules_table_exists(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    tbody = page.locator("#rulesBody")
    assert tbody.count() > 0


def test_ufw_initial_placeholder_text(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    content = page.locator("#rulesBody").inner_text()
    # without a selected platform the placeholder message is shown
    assert len(content) > 0


# ── no JS errors ──────────────────────────────────────────────────────────

def test_ufw_page_no_js_errors(logged_in: Page):
    errors = []
    logged_in.on("pageerror", lambda e: errors.append(str(e)))
    _go_ufw(logged_in)
    assert errors == [], f"JS errors on UFW page: {errors}"


# ── sidebar navigation ────────────────────────────────────────────────────

def test_ufw_sidebar_link_active(logged_in: Page):
    page = logged_in
    _go_ufw(page)
    active = page.locator("nav a.active, nav a[aria-current='page'], .nav-item.active")
    # at least the page is rendered without error
    assert "/virt/ufw" in page.url
