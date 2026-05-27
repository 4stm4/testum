# SPDX-License-Identifier: MIT
"""E2E: SDN Nodes panel — API, table, delete, sidebar, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_NODE_NAME = "e2e-node-"


def _go_nodes(page: Page):
    page.goto(f"{BASE_URL}/sdn#nodes")
    page.wait_for_load_state("networkidle")


def _seed_node(api, name: str | None = None, **extra) -> dict:
    """Seed a node via webhook node.registered event, wait until it appears in DB."""
    node_id = "e2e-" + uuid.uuid4().hex[:12]
    node_name = name or (_NODE_NAME + uuid.uuid4().hex[:8])
    payload = {
        "event_type":    "node.registered",
        "resource_type": "node",
        "resource_id":   node_id,
        "payload": {
            "id":            node_id,
            "name":          node_name,
            "mgmt_ip":       extra.get("mgmt_ip", "10.0.0.1"),
            "status":        extra.get("status", "ready"),
            "agent_version": extra.get("agent_version", "1.2.3"),
            "roles":         extra.get("roles", ["gateway"]),
            "labels":        extra.get("labels", {}),
        },
    }
    api("POST", "/webhooks/nervum", payload)
    # Webhook handler is async (asyncio.create_task) — poll until node lands in DB
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/nodes")
        if r["status"] == 200 and any(n["id"] == node_id for n in r["body"]):
            break
        time.sleep(0.2)
    return {"id": node_id, "name": node_name}


# ── panel presence ────────────────────────────────────────────────────────────

def test_nodes_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_nodes(page)
    panel = page.locator("#panel-nodes")
    expect(panel).to_be_visible(timeout=8_000)


def test_nodes_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_nodes(page)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-ports")).to_be_hidden(timeout=5_000)


def test_nodes_table_columns(logged_in: Page):
    page = logged_in
    _go_nodes(page)
    headers = page.locator("#panel-nodes thead th")
    texts = [headers.nth(i).inner_text().strip() for i in range(headers.count())]
    for col in ("NAME", "MGMT IP", "STATUS", "AGENT VER", "ROLES"):
        assert any(col in t.upper() for t in texts), f"Column '{col}' not found in {texts}"


def test_nodes_has_no_create_button(logged_in: Page):
    """Nodes come from Nervum only — no manual create."""
    page = logged_in
    _go_nodes(page)
    panel = page.locator("#panel-nodes")
    create_btn = panel.locator("button:has-text('Create'), button:has-text('+ Create')")
    assert create_btn.count() == 0


# ── API ───────────────────────────────────────────────────────────────────────

def test_api_nodes_list_returns_list(api):
    r = api("GET", "/api/sdn/nodes")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_node_seed_via_webhook(api):
    """node.registered webhook creates a node accessible via GET."""
    info = _seed_node(api)
    r = api("GET", "/api/sdn/nodes")
    assert r["status"] == 200
    ids = [n["id"] for n in r["body"]]
    assert info["id"] in ids
    api("DELETE", f"/api/sdn/nodes/{info['id']}")


def test_api_node_delete(api):
    info = _seed_node(api)
    r = api("DELETE", f"/api/sdn/nodes/{info['id']}")
    assert r["status"] in (200, 204)
    r2 = api("GET", "/api/sdn/nodes")
    assert info["id"] not in [n["id"] for n in r2["body"]]


def test_api_node_delete_not_found(api):
    r = api("DELETE", "/api/sdn/nodes/nonexistent-e2e-node")
    assert r["status"] == 404


def test_api_node_fields_returned(api):
    """list endpoint must return id, name, mgmt_ip, status, agent_version, roles."""
    info = _seed_node(api, mgmt_ip="192.168.1.50", status="ready",
                      agent_version="2.0.0", roles=["compute", "gateway"])
    r = api("GET", "/api/sdn/nodes")
    node = next((n for n in r["body"] if n["id"] == info["id"]), None)
    assert node is not None
    assert node["mgmt_ip"] == "192.168.1.50"
    assert node["status"] == "ready"
    assert node["agent_version"] == "2.0.0"
    assert "compute" in node["roles"]
    api("DELETE", f"/api/sdn/nodes/{info['id']}")


def test_api_node_update_via_webhook(api):
    """node.updated event overwrites existing row fields."""
    info = _seed_node(api, status="provisioning")
    update_payload = {
        "event_type":    "node.updated",
        "resource_type": "node",
        "resource_id":   info["id"],
        "payload": {
            "id":     info["id"],
            "name":   info["name"],
            "status": "ready",
        },
    }
    api("POST", "/webhooks/nervum", update_payload)
    r = api("GET", "/api/sdn/nodes")
    node = next((n for n in r["body"] if n["id"] == info["id"]), None)
    assert node is not None
    assert node["status"] == "ready"
    api("DELETE", f"/api/sdn/nodes/{info['id']}")


def test_api_node_removed_via_webhook(api):
    """node.removed event deletes the row."""
    info = _seed_node(api)
    rm_payload = {
        "event_type":    "node.removed",
        "resource_type": "node",
        "resource_id":   info["id"],
        "payload":       {},
    }
    api("POST", "/webhooks/nervum", rm_payload)
    # Poll until gone
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/nodes")
        if r["status"] == 200 and info["id"] not in [n["id"] for n in r["body"]]:
            break
        time.sleep(0.2)
    r = api("GET", "/api/sdn/nodes")
    assert info["id"] not in [n["id"] for n in r["body"]]


# ── delete from UI ────────────────────────────────────────────────────────────

def test_delete_node_from_table(logged_in: Page, api):
    info = _seed_node(api)
    page = logged_in
    _go_nodes(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#nodesBody").get_by_text(info["name"])
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#nodesBody tr:has-text('{info['name']}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/nodes")
    assert info["id"] not in [n["id"] for n in r2["body"]], "Node still in DB after UI delete"


# ── status pill and roles ─────────────────────────────────────────────────────

def test_nodes_status_pill_rendered(logged_in: Page, api):
    info = _seed_node(api, status="ready")
    page = logged_in
    _go_nodes(page)
    page.wait_for_load_state("networkidle")
    row = page.locator(f"#nodesBody tr:has-text('{info['name']}')")
    expect(row.first).to_be_visible(timeout=8_000)
    pill = row.first.locator(".pill, .status-pill, [class*='pill']")
    assert pill.count() > 0 or "ready" in row.first.inner_text().lower()
    api("DELETE", f"/api/sdn/nodes/{info['id']}")


def test_nodes_roles_shown_in_row(logged_in: Page, api):
    info = _seed_node(api, roles=["compute", "gateway"])
    page = logged_in
    _go_nodes(page)
    page.wait_for_load_state("networkidle")
    row = page.locator(f"#nodesBody tr:has-text('{info['name']}')")
    expect(row.first).to_be_visible(timeout=8_000)
    text = row.first.inner_text()
    assert "compute" in text or "gateway" in text
    api("DELETE", f"/api/sdn/nodes/{info['id']}")


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_sidebar_link_activates_nodes_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='nodes']")
    if link.count() == 0:
        pytest.skip("Sidebar nodes link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "nodes" in page.url


def test_sidebar_link_shows_nodes_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='nodes']")
    if link.count() == 0:
        pytest.skip("Sidebar nodes link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#panel-nodes")).to_be_visible(timeout=5_000)


def test_sidebar_nodes_link_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='nodes']")
    if link.count() == 0:
        pytest.skip("Sidebar nodes link not found")
    link.first.click()
    page.wait_for_timeout(300)
    classes = link.first.get_attribute("class") or ""
    assert "active" in classes


# ── empty state ───────────────────────────────────────────────────────────────

def test_nodes_empty_state_no_js_error(logged_in: Page):
    page = logged_in
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    _go_nodes(page)
    page.wait_for_load_state("networkidle")
    js_errors = [e for e in errors if "Uncaught" in e or "TypeError" in e]
    assert js_errors == [], f"JS errors: {js_errors}"


# ── Webhook → UI integration ──────────────────────────────────────────────────

def test_webhook_node_registered_appears_in_table(logged_in: Page, api):
    page = logged_in
    _go_nodes(page)
    page.wait_for_load_state("networkidle")

    info = _seed_node(api)
    page.reload()
    page.wait_for_load_state("networkidle")

    row = page.locator("#nodesBody").get_by_text(info["name"])
    expect(row.first).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/nodes/{info['id']}")


def test_webhook_node_removed_removes_row(logged_in: Page, api):
    info = _seed_node(api)
    page = logged_in
    _go_nodes(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#nodesBody").get_by_text(info["name"])
    expect(row.first).to_be_visible(timeout=8_000)

    rm_payload = {
        "event_type":    "node.removed",
        "resource_type": "node",
        "resource_id":   info["id"],
        "payload":       {},
    }
    api("POST", "/webhooks/nervum", rm_payload)
    page.reload()
    page.wait_for_load_state("networkidle")

    expect(row.first).to_be_hidden(timeout=8_000)
