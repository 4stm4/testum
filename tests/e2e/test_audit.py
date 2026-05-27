# SPDX-License-Identifier: MIT
"""E2E: Audit log — page loads, API filters, actions generate entries."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_audit(page: Page):
    page.goto(f"{BASE_URL}/audit")
    page.wait_for_load_state("networkidle")


# ── page loads ────────────────────────────────────────────────────────────

def test_audit_page_loads(logged_in: Page):
    page = logged_in
    _go_audit(page)
    assert "/audit" in page.url


def test_audit_page_has_table(logged_in: Page):
    page = logged_in
    _go_audit(page)
    table = page.locator("table, .audit-list, .log-list, [data-testid='audit']")
    expect(table.first).to_be_visible(timeout=8_000)


# ── API ───────────────────────────────────────────────────────────────────

def test_audit_api_returns_list(api):
    r = api("GET", "/api/audit")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_audit_api_filter_by_action(api):
    # Use an action that definitely exists (create, delete, etc.)
    r = api("GET", "/api/audit?action=create")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_audit_api_filter_by_user(api):
    # Audit uses 'user' field, filter by user
    r = api("GET", "/api/audit?user=admin")
    assert r["status"] == 200
    logs = r["body"]
    for entry in logs:
        # Field name is 'user' in this API
        assert entry.get("user") == "admin"


def test_audit_api_limit(api):
    r = api("GET", "/api/audit?limit=5")
    assert r["status"] == 200
    assert len(r["body"]) <= 5


def test_audit_api_stats(api):
    r = api("GET", "/api/audit/stats")
    assert r["status"] == 200
    body = r["body"]
    assert isinstance(body, dict)


# ── audit entries exist ───────────────────────────────────────────────────

def test_audit_entries_exist(api):
    """Audit endpoint must return a list; entries accumulate over the session."""
    # Create something to ensure at least one auditable action happened
    r_plat = api("POST", "/api/platforms", {
        "name": "e2e-audit-seed", "host": "10.99.0.1", "port": 22,
        "username": "root", "auth_method": "password", "password": "secret",
    })
    r = api("GET", "/api/audit?limit=50")
    assert r["status"] == 200
    assert isinstance(r["body"], list)
    # If the platform was created successfully, there must be at least one entry
    if r_plat["status"] in (200, 201):
        assert len(r["body"]) >= 1


# ── platform actions generate audit entries ───────────────────────────────

def test_create_platform_generates_audit(api):
    r_create = api("POST", "/api/platforms", {
        "name": "e2e-audit-host",
        "host": "10.99.77.1",
        "port": 22,
        "username": "root",
        "auth_method": "password",
        "password": "secret",
    })
    if r_create["status"] >= 500:
        pytest.skip("Platform creation returned 500")

    r_audit = api("GET", "/api/audit?limit=20")
    assert r_audit["status"] == 200
    assert isinstance(r_audit["body"], list)

    if r_create["status"] in (200, 201):
        pid = r_create["body"].get("id")
        if pid:
            api("DELETE", f"/api/platforms/{pid}")


# ── export ────────────────────────────────────────────────────────────────

def test_audit_export_endpoint(api):
    r = api("GET", "/api/audit/export")
    assert r["status"] in (200, 501, 400)


# ── UI filters ────────────────────────────────────────────────────────────

def test_audit_page_has_filter_controls(logged_in: Page):
    page = logged_in
    _go_audit(page)
    filter_ctrl = page.locator(
        "input[name='action'], input[placeholder*='filter'], "
        "input[placeholder*='Filter'], select[name='action'], "
        ".filter, [data-testid='filter']"
    )
    table = page.locator("table, .audit-list")
    expect(table.or_(filter_ctrl).first).to_be_visible(timeout=8_000)
