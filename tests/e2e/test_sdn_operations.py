# SPDX-License-Identifier: MIT
"""E2E: SDN Operations panel — read-only, API filters, sidebar navigation."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_ops(page: Page):
    page.goto(f"{BASE_URL}/sdn#ops")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='ops']")
    if link.count():
        link.first.click()
        page.wait_for_timeout(400)


# ── panel presence ────────────────────────────────────────────────────────────

def test_ops_panel_active_on_hash(logged_in: Page):
    """Navigating to sdn#ops must make #panel-ops visible."""
    page = logged_in
    _go_ops(page)
    expect(page.locator("#panel-ops")).to_be_visible(timeout=8_000)


def test_ops_other_panels_hidden(logged_in: Page):
    """#panel-networks must be hidden when ops tab is active."""
    page = logged_in
    _go_ops(page)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)


def test_ops_has_no_create_button(logged_in: Page):
    """Operations panel is read-only — no '+ Create' button should exist."""
    page = logged_in
    _go_ops(page)
    panel = page.locator("#panel-ops")
    create_btn = panel.locator(
        "button:has-text('Create'), button:has-text('+ Create'), button:has-text('Add')"
    )
    assert create_btn.count() == 0, "Create button must not exist in read-only Operations panel"


def test_ops_table_columns(logged_in: Page):
    """Operations thead must contain at least one meaningful column header."""
    page = logged_in
    _go_ops(page)
    panel = page.locator("#panel-ops")
    headers = panel.locator("thead th").all_inner_texts()
    assert len(headers) > 0, "Operations table has no column headers"
    combined = " ".join(h.lower() for h in headers)
    assert any(kw in combined for kw in ("id", "status", "kind", "type", "task", "network")), (
        f"No expected column keywords found in: {headers}"
    )


# ── API: list + filters ───────────────────────────────────────────────────────

def test_api_operations_list_returns_list(api):
    """GET /api/sdn/operations must return 200 and a JSON list."""
    r = api("GET", "/api/sdn/operations")
    assert r["status"] == 200, f"Expected 200, got {r['status']}"
    assert isinstance(r["body"], list), f"Expected list, got {type(r['body'])}"


def test_api_operations_filter_by_status(api):
    """GET /api/sdn/operations?status=running must return 200 and a list."""
    r = api("GET", "/api/sdn/operations?status=running")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_operations_filter_by_network_id(api):
    """GET /api/sdn/operations?network_id=some-net must return 200 and a list."""
    r = api("GET", "/api/sdn/operations?network_id=some-net")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_operations_limit(api):
    """GET /api/sdn/operations?limit=5 must return at most 5 items."""
    r = api("GET", "/api/sdn/operations?limit=5")
    assert r["status"] == 200
    assert isinstance(r["body"], list)
    assert len(r["body"]) <= 5, f"Expected ≤5 items with limit=5, got {len(r['body'])}"


def test_api_operations_get_not_found(api):
    """GET /api/sdn/operations/nonexistent must return 404."""
    r = api("GET", "/api/sdn/operations/nonexistent-task-id-that-does-not-exist")
    assert r["status"] == 404, f"Expected 404, got {r['status']}"


def test_api_operations_returns_correct_schema(api):
    """If the operations list is non-empty, each item must have id and status fields."""
    r = api("GET", "/api/sdn/operations")
    assert r["status"] == 200
    items = r["body"]
    if not items:
        pytest.skip("No operations present — skipping schema check")
    first = items[0]
    assert "id" in first, f"'id' field missing from operation: {first}"
    assert "status" in first, f"'status' field missing from operation: {first}"


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_ops_sidebar_link_activates_hash(logged_in: Page):
    """Clicking [data-sdn-tab='ops'] must put #ops in the URL."""
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")

    link = page.locator("[data-sdn-tab='ops']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='ops'] not found")

    link.first.click()
    page.wait_for_timeout(300)
    assert "ops" in page.url, f"Expected 'ops' in URL after clicking tab, got: {page.url}"


def test_ops_sidebar_shows_panel(logged_in: Page):
    """Clicking sidebar ops link must show #panel-ops."""
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")

    link = page.locator("[data-sdn-tab='ops']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='ops'] not found")

    link.first.click()
    expect(page.locator("#panel-ops")).to_be_visible(timeout=5_000)


def test_ops_sidebar_active_class(logged_in: Page):
    """Active sidebar ops link must receive .active CSS class."""
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")

    link = page.locator("[data-sdn-tab='ops']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='ops'] not found")

    link.first.click()
    page.wait_for_timeout(300)
    classes = link.first.get_attribute("class") or ""
    assert "active" in classes, f"Expected .active class on ops sidebar link, got: {classes!r}"


# ── empty state / error checks ────────────────────────────────────────────────

def test_ops_empty_state_no_js_errors(logged_in: Page):
    """Operations panel must load without JavaScript exceptions."""
    page = logged_in
    js_errors: list[str] = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    _go_ops(page)
    page.wait_for_load_state("networkidle")

    assert not js_errors, f"JS errors on SDN Operations page: {js_errors}"


def test_ops_page_loads_without_error(logged_in: Page):
    """Operations tbody must not contain 'Failed to load' text on initial render."""
    page = logged_in
    _go_ops(page)
    page.wait_for_load_state("networkidle")

    tbody = page.locator("#opsBody")
    if tbody.count() == 0:
        # Fall back to panel-ops tbody
        tbody = page.locator("#panel-ops tbody")

    page.wait_for_timeout(1_000)
    text = tbody.inner_text() if tbody.count() > 0 else ""
    assert "Failed to load" not in text, f"Error text found in ops tbody: {text!r}"
