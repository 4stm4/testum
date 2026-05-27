# SPDX-License-Identifier: MIT
"""E2E: SDN Logical Ports panel — Create form, API CRUD, table, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_PORT_NAME = "e2e-port-"
_NET_ID    = "e2e-net-fixture"


def _go_ports(page: Page):
    page.goto(f"{BASE_URL}/sdn#ports")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page):
    panel = page.locator("#panel-ports")
    panel.locator("button:has-text('Create'), button:has-text('+ Create')").first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


def _seed_port(api, name: str | None = None, **extra) -> dict:
    """Seed a logical port via webhook. Polls until it lands in DB."""
    port_id   = "e2e-lp-" + uuid.uuid4().hex[:10]
    port_name = name or (_PORT_NAME + uuid.uuid4().hex[:8])
    payload = {
        "event_type":    "logical_port.created",
        "resource_type": "logical_port",
        "resource_id":   port_id,
        "project_id":    extra.get("project_id"),
        "payload": {
            "id":         port_id,
            "name":       port_name,
            "network_id": extra.get("network_id", _NET_ID),
            "project_id": extra.get("project_id"),
            "status":     extra.get("status", "active"),
            "mac":        extra.get("mac"),
            "ip_address": extra.get("ip_address"),
        },
    }
    api("POST", "/webhooks/nervum", payload)
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/logical-ports")
        if r["status"] == 200 and any(p["id"] == port_id for p in r["body"]):
            break
        time.sleep(0.2)
    return {"id": port_id, "name": port_name}


# ── panel presence ────────────────────────────────────────────────────────────

def test_ports_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_ports(page)
    expect(page.locator("#panel-ports")).to_be_visible(timeout=8_000)


def test_ports_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_ports(page)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-nodes")).to_be_hidden(timeout=5_000)


def test_ports_table_columns(logged_in: Page):
    page = logged_in
    _go_ports(page)
    headers = page.locator("#panel-ports thead th")
    texts = [headers.nth(i).inner_text().strip().upper() for i in range(headers.count())]
    for col in ("NAME", "NETWORK", "STATUS"):
        assert any(col in t for t in texts), f"Column '{col}' not found in {texts}"


def test_ports_has_create_button(logged_in: Page):
    page = logged_in
    _go_ports(page)
    btn = page.locator("#panel-ports button:has-text('Create'), #panel-ports button:has-text('+ Create')")
    expect(btn.first).to_be_visible(timeout=5_000)


# ── modal open / close ────────────────────────────────────────────────────────

def test_create_modal_opens(logged_in: Page):
    page = logged_in
    _go_ports(page)
    _open_create_modal(page)
    expect(page.locator("#createModal")).to_be_visible(timeout=5_000)


def test_create_modal_title(logged_in: Page):
    page = logged_in
    _go_ports(page)
    _open_create_modal(page)
    title = page.locator("#createModalTitle").inner_text()
    assert "port" in title.lower() or "ports" in title.lower()


def test_create_modal_has_name_field(logged_in: Page):
    page = logged_in
    _go_ports(page)
    _open_create_modal(page)
    expect(page.locator("#cf_name")).to_be_visible(timeout=3_000)


def test_create_modal_has_network_id_field(logged_in: Page):
    page = logged_in
    _go_ports(page)
    _open_create_modal(page)
    expect(page.locator("#cf_network_id")).to_be_visible(timeout=3_000)


def test_create_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_ports(page)
    _open_create_modal(page)
    page.locator("#createModal button:has-text('Cancel'), #createCancelBtn").first.click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


def test_create_modal_backdrop_click_closes(logged_in: Page):
    page = logged_in
    _go_ports(page)
    _open_create_modal(page)
    page.locator("#createModal").click(position={"x": 5, "y": 5})
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


# ── client-side validation ────────────────────────────────────────────────────

def test_create_empty_name_keeps_modal_open(logged_in: Page):
    page = logged_in
    _go_ports(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill("")
    page.locator("#cf_network_id").fill("some-net")
    page.locator("#createSubmitBtn").click()
    expect(page.locator("#createModal")).to_be_visible(timeout=3_000)


def test_create_empty_network_id_keeps_modal_open(logged_in: Page):
    page = logged_in
    _go_ports(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill("test-port")
    page.locator("#cf_network_id").fill("")
    page.locator("#createSubmitBtn").click()
    expect(page.locator("#createModal")).to_be_visible(timeout=3_000)


# ── successful create ─────────────────────────────────────────────────────────

def test_create_port_name_and_network(logged_in: Page, api):
    name = _PORT_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_ports(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    page.locator("#cf_network_id").fill("net-e2e-fixture")

    with page.expect_response(
        lambda r: "/api/sdn/logical-ports" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    port_id = resp.value.json().get("id")
    if port_id:
        api("DELETE", f"/api/sdn/logical-ports/{port_id}")


def test_create_port_all_fields(logged_in: Page, api):
    name = _PORT_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_ports(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    page.locator("#cf_network_id").fill("net-e2e-all")
    page.locator("#cf_project_id").fill("proj-e2e")

    with page.expect_response(
        lambda r: "/api/sdn/logical-ports" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    body = resp.value.json()
    port_id = body.get("id")
    assert port_id
    if port_id:
        api("DELETE", f"/api/sdn/logical-ports/{port_id}")


def test_create_port_status_pending(api):
    """Newly created port via API has status 'pending'."""
    name = _PORT_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/logical-ports", {"name": name, "network_id": "net-fixture"})
    assert r["status"] in (200, 201)
    port_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/logical-ports/{port_id}")
    assert r2["body"]["status"] == "pending"
    api("DELETE", f"/api/sdn/logical-ports/{port_id}")


# ── table update after create ─────────────────────────────────────────────────

def test_created_port_appears_in_table(logged_in: Page, api):
    name = _PORT_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_ports(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    page.locator("#cf_network_id").fill("net-e2e-table")

    with page.expect_response(
        lambda r: "/api/sdn/logical-ports" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    port_id = resp.value.json().get("id")

    row = page.locator("#portsBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    if port_id:
        api("DELETE", f"/api/sdn/logical-ports/{port_id}")


# ── delete from UI ────────────────────────────────────────────────────────────

def test_delete_port_from_table(logged_in: Page, api):
    name = _PORT_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/logical-ports", {"name": name, "network_id": "net-e2e-del"})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create port via API")
    port_id = r["body"]["id"]

    page = logged_in
    _go_ports(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#portsBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#portsBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/logical-ports")
    assert port_id not in [p["id"] for p in r2["body"]]


# ── full roundtrip ────────────────────────────────────────────────────────────

def test_create_and_delete_full_roundtrip(logged_in: Page):
    name = _PORT_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_ports(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    page.locator("#cf_network_id").fill("net-e2e-rt")

    with page.expect_response(
        lambda r: "/api/sdn/logical-ports" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)

    row = page.locator("#portsBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#portsBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_api_list_returns_list(api):
    r = api("GET", "/api/sdn/logical-ports")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_create_minimal(api):
    name = _PORT_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/logical-ports", {"name": name, "network_id": "net-api-min"})
    assert r["status"] in (200, 201)
    assert r["body"].get("id")
    api("DELETE", f"/api/sdn/logical-ports/{r['body']['id']}")


def test_api_create_all_fields(api):
    name = _PORT_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/logical-ports", {
        "name": name, "network_id": "net-api-all", "project_id": "proj-e2e",
    })
    assert r["status"] in (200, 201)
    port_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/logical-ports/{port_id}")
    assert r2["body"]["project_id"] == "proj-e2e"
    assert r2["body"]["network_id"] == "net-api-all"
    api("DELETE", f"/api/sdn/logical-ports/{port_id}")


def test_api_create_missing_name_returns_422(api):
    r = api("POST", "/api/sdn/logical-ports", {"network_id": "net-abc"})
    assert r["status"] == 422


def test_api_get_single_port(api):
    name = _PORT_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/logical-ports", {"name": name, "network_id": "net-single"})
    port_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/logical-ports/{port_id}")
    assert r2["status"] == 200
    assert r2["body"]["id"] == port_id
    assert r2["body"]["name"] == name
    api("DELETE", f"/api/sdn/logical-ports/{port_id}")


def test_api_get_single_port_not_found(api):
    r = api("GET", "/api/sdn/logical-ports/nonexistent-e2e-port")
    assert r["status"] == 404


def test_api_delete_port(api):
    r = api("POST", "/api/sdn/logical-ports", {
        "name": _PORT_NAME + uuid.uuid4().hex[:8], "network_id": "net-del",
    })
    port_id = r["body"]["id"]
    r2 = api("DELETE", f"/api/sdn/logical-ports/{port_id}")
    assert r2["status"] in (200, 204)
    r3 = api("GET", f"/api/sdn/logical-ports/{port_id}")
    assert r3["status"] == 404


def test_api_delete_not_found(api):
    r = api("DELETE", "/api/sdn/logical-ports/nonexistent-e2e-port")
    assert r["status"] == 404


def test_api_filter_by_project_id(api):
    pid = "proj-filter-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/logical-ports", {
        "name": _PORT_NAME + uuid.uuid4().hex[:8], "network_id": "net-f", "project_id": pid,
    })
    port_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/logical-ports?project_id={pid}")
    assert r2["status"] == 200
    ids = [p["id"] for p in r2["body"]]
    assert port_id in ids
    for p in r2["body"]:
        assert p["project_id"] == pid
    api("DELETE", f"/api/sdn/logical-ports/{port_id}")


def test_api_filter_by_network_id(api):
    net = "net-filter-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/logical-ports", {
        "name": _PORT_NAME + uuid.uuid4().hex[:8], "network_id": net,
    })
    port_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/logical-ports?network_id={net}")
    assert r2["status"] == 200
    ids = [p["id"] for p in r2["body"]]
    assert port_id in ids
    for p in r2["body"]:
        assert p["network_id"] == net
    api("DELETE", f"/api/sdn/logical-ports/{port_id}")


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_sidebar_link_activates_ports_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='ports']")
    if link.count() == 0:
        pytest.skip("Sidebar ports link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "ports" in page.url


def test_sidebar_link_shows_ports_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='ports']")
    if link.count() == 0:
        pytest.skip("Sidebar ports link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#panel-ports")).to_be_visible(timeout=5_000)


def test_sidebar_ports_link_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='ports']")
    if link.count() == 0:
        pytest.skip("Sidebar ports link not found")
    link.first.click()
    page.wait_for_timeout(300)
    classes = link.first.get_attribute("class") or ""
    assert "active" in classes


# ── empty state ───────────────────────────────────────────────────────────────

def test_ports_empty_state_no_js_error(logged_in: Page):
    page = logged_in
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    _go_ports(page)
    page.wait_for_load_state("networkidle")
    js_errors = [e for e in errors if "Uncaught" in e or "TypeError" in e]
    assert js_errors == [], f"JS errors: {js_errors}"


# ── Webhook → UI integration ──────────────────────────────────────────────────

def test_webhook_port_created_appears_in_table(logged_in: Page, api):
    page = logged_in
    _go_ports(page)
    page.wait_for_load_state("networkidle")

    info = _seed_port(api)
    page.reload()
    page.wait_for_load_state("networkidle")

    row = page.locator("#portsBody").get_by_text(info["name"])
    expect(row.first).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/logical-ports/{info['id']}")


def test_webhook_port_deleted_removes_row(logged_in: Page, api):
    info = _seed_port(api)
    page = logged_in
    _go_ports(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#portsBody").get_by_text(info["name"])
    expect(row.first).to_be_visible(timeout=8_000)

    rm_payload = {
        "event_type":    "logical_port.deleted",
        "resource_type": "logical_port",
        "resource_id":   info["id"],
        "payload":       {},
    }
    api("POST", "/webhooks/nervum", rm_payload)
    page.reload()
    page.wait_for_load_state("networkidle")

    expect(row.first).to_be_hidden(timeout=8_000)


def test_webhook_port_status_updated(api):
    """logical_port.status_changed updates status field in replica."""
    info = _seed_port(api, status="pending")
    upd = {
        "event_type":    "logical_port.status_changed",
        "resource_type": "logical_port",
        "resource_id":   info["id"],
        "payload":       {"id": info["id"], "name": info["name"], "status": "active"},
    }
    api("POST", "/webhooks/nervum", upd)
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", f"/api/sdn/logical-ports/{info['id']}")
        if r["status"] == 200 and r["body"].get("status") == "active":
            break
        time.sleep(0.2)
    r = api("GET", f"/api/sdn/logical-ports/{info['id']}")
    assert r["body"]["status"] == "active"
    api("DELETE", f"/api/sdn/logical-ports/{info['id']}")
