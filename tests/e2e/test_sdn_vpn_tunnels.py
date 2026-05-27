# SPDX-License-Identifier: MIT
"""E2E: SDN VPN Tunnels panel — Create form, API CRUD, table, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_VPN_NAME = "e2e-vpn-"


def _go_vpn(page: Page):
    page.goto(f"{BASE_URL}/sdn#vpn")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page):
    page.locator(
        "#panel-vpn button:has-text('Create'), #panel-vpn button:has-text('+ Create')"
    ).first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


def _seed_vpn_tunnel(api, name: str | None = None, **extra) -> dict:
    """Seed a VPN tunnel via webhook. Polls until it lands in DB."""
    tun_id = "e2e-vpn-" + uuid.uuid4().hex[:10]
    tun_name = name or (_VPN_NAME + uuid.uuid4().hex[:8])
    payload = {
        "event_type": "vpn_tunnel.created",
        "resource_type": "vpn_tunnel",
        "resource_id": tun_id,
        "project_id": extra.get("project_id"),
        "payload": {
            "id": tun_id,
            "name": tun_name,
            "project_id": extra.get("project_id"),
            "protocol": extra.get("protocol", "wireguard"),
            "status": extra.get("status", "build"),
        },
    }
    api("POST", "/webhooks/nervum", payload)
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/vpn-tunnels")
        if r["status"] == 200 and any(x["id"] == tun_id for x in r["body"]):
            break
        time.sleep(0.2)
    return {"id": tun_id, "name": tun_name}


# ── panel presence ────────────────────────────────────────────────────────────

def test_vpn_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_vpn(page)
    expect(page.locator("#panel-vpn")).to_be_visible(timeout=8_000)


def test_vpn_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_vpn(page)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-routers")).to_be_hidden(timeout=5_000)


def test_vpn_table_columns(logged_in: Page):
    page = logged_in
    _go_vpn(page)
    headers = page.locator("#panel-vpn thead th")
    texts = [headers.nth(i).inner_text().strip().upper() for i in range(headers.count())]
    for col in ("NAME", "PROTOCOL", "STATUS"):
        assert any(col in t for t in texts), f"Column '{col}' not found in {texts}"


def test_vpn_has_create_button(logged_in: Page):
    page = logged_in
    _go_vpn(page)
    expect(
        page.locator(
            "#panel-vpn button:has-text('Create'), #panel-vpn button:has-text('+ Create')"
        ).first
    ).to_be_visible(timeout=5_000)


# ── modal open / close ────────────────────────────────────────────────────────

def test_create_modal_opens(logged_in: Page):
    page = logged_in
    _go_vpn(page)
    _open_create_modal(page)
    expect(page.locator("#createModal")).to_be_visible(timeout=5_000)


def test_create_modal_title(logged_in: Page):
    page = logged_in
    _go_vpn(page)
    _open_create_modal(page)
    title = page.locator("#createModalTitle").inner_text()
    assert "vpn" in title.lower() or "tunnel" in title.lower()


def test_create_modal_has_name_field(logged_in: Page):
    page = logged_in
    _go_vpn(page)
    _open_create_modal(page)
    expect(page.locator("#cf_name")).to_be_visible(timeout=3_000)


def test_create_modal_has_protocol_field(logged_in: Page):
    page = logged_in
    _go_vpn(page)
    _open_create_modal(page)
    expect(page.locator("#cf_protocol")).to_be_visible(timeout=3_000)


def test_create_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_vpn(page)
    _open_create_modal(page)
    page.locator(
        "#createModal button:has-text('Cancel'), #createCancelBtn"
    ).first.click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


# ── client-side validation ────────────────────────────────────────────────────

def test_create_empty_name_keeps_modal_open(logged_in: Page):
    page = logged_in
    _go_vpn(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill("")
    page.locator("#createSubmitBtn").click()
    expect(page.locator("#createModal")).to_be_visible(timeout=3_000)


# ── successful create ─────────────────────────────────────────────────────────

def test_create_vpn_tunnel_name_only(logged_in: Page, api):
    name = _VPN_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_vpn(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/vpn-tunnels" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    tun_id = resp.value.json().get("id")
    if tun_id:
        api("DELETE", f"/api/sdn/vpn-tunnels/{tun_id}")


def test_create_vpn_tunnel_protocol_wireguard(logged_in: Page, api):
    name = _VPN_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_vpn(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    proto_field = page.locator("#cf_protocol")
    if proto_field.evaluate("el => el.tagName") == "SELECT":
        proto_field.select_option("wireguard")
    else:
        proto_field.fill("wireguard")

    with page.expect_response(
        lambda r: "/api/sdn/vpn-tunnels" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    tun_id = resp.value.json().get("id")
    if tun_id:
        r2 = api("GET", "/api/sdn/vpn-tunnels")
        tun = next((x for x in r2["body"] if x["id"] == tun_id), None)
        assert tun and tun["protocol"] == "wireguard"
        api("DELETE", f"/api/sdn/vpn-tunnels/{tun_id}")


def test_create_vpn_tunnel_protocol_ipsec(logged_in: Page, api):
    name = _VPN_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_vpn(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    proto_field = page.locator("#cf_protocol")
    if proto_field.evaluate("el => el.tagName") == "SELECT":
        proto_field.select_option("ipsec")
    else:
        proto_field.fill("ipsec")

    with page.expect_response(
        lambda r: "/api/sdn/vpn-tunnels" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    tun_id = resp.value.json().get("id")
    if tun_id:
        r2 = api("GET", "/api/sdn/vpn-tunnels")
        tun = next((x for x in r2["body"] if x["id"] == tun_id), None)
        assert tun and tun["protocol"] == "ipsec"
        api("DELETE", f"/api/sdn/vpn-tunnels/{tun_id}")


def test_vpn_tunnel_initial_status_is_build(api):
    """Newly created VPN tunnel has status 'build'."""
    name = _VPN_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/vpn-tunnels", {"name": name})
    assert r["status"] in (200, 201)
    tun_id = r["body"]["id"]
    r2 = api("GET", "/api/sdn/vpn-tunnels")
    tun = next((x for x in r2["body"] if x["id"] == tun_id), None)
    assert tun is not None
    assert tun["status"] == "build"
    api("DELETE", f"/api/sdn/vpn-tunnels/{tun_id}")


def test_created_vpn_tunnel_appears_in_table(logged_in: Page, api):
    name = _VPN_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_vpn(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/vpn-tunnels" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    tun_id = resp.value.json().get("id")

    row = page.locator("#vpnBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    if tun_id:
        api("DELETE", f"/api/sdn/vpn-tunnels/{tun_id}")


# ── delete from UI ────────────────────────────────────────────────────────────

def test_delete_vpn_tunnel_from_table(logged_in: Page, api):
    name = _VPN_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/vpn-tunnels", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create VPN tunnel via API")
    tun_id = r["body"]["id"]

    page = logged_in
    _go_vpn(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#vpnBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#vpnBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/vpn-tunnels")
    assert tun_id not in [x["id"] for x in r2["body"]]


# ── full roundtrip ────────────────────────────────────────────────────────────

def test_create_and_delete_full_roundtrip(logged_in: Page):
    name = _VPN_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_vpn(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/vpn-tunnels" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)

    row = page.locator("#vpnBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#vpnBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_api_list_returns_list(api):
    r = api("GET", "/api/sdn/vpn-tunnels")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_create_minimal(api):
    name = _VPN_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/vpn-tunnels", {"name": name})
    assert r["status"] in (200, 201)
    assert r["body"].get("id")
    api("DELETE", f"/api/sdn/vpn-tunnels/{r['body']['id']}")


def test_api_create_missing_name_returns_422(api):
    r = api("POST", "/api/sdn/vpn-tunnels", {"project_id": "proj-abc"})
    assert r["status"] == 422


def test_api_delete_vpn_tunnel(api):
    name = _VPN_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/vpn-tunnels", {"name": name})
    assert r["status"] in (200, 201)
    tun_id = r["body"]["id"]
    r2 = api("DELETE", f"/api/sdn/vpn-tunnels/{tun_id}")
    assert r2["status"] in (200, 204)
    r3 = api("GET", "/api/sdn/vpn-tunnels")
    assert tun_id not in [x["id"] for x in r3["body"]]


def test_api_delete_vpn_tunnel_not_found(api):
    r = api("DELETE", "/api/sdn/vpn-tunnels/nonexistent-e2e-vpn")
    assert r["status"] == 404


def test_api_vpn_project_filter(api):
    pid = "proj-vpn-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/vpn-tunnels", {
        "name": _VPN_NAME + uuid.uuid4().hex[:8],
        "project_id": pid,
    })
    assert r["status"] in (200, 201)
    tun_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/vpn-tunnels?project_id={pid}")
    assert r2["status"] == 200
    ids = [x["id"] for x in r2["body"]]
    assert tun_id in ids
    for x in r2["body"]:
        assert x["project_id"] == pid
    api("DELETE", f"/api/sdn/vpn-tunnels/{tun_id}")


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_sidebar_link_activates_vpn_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='vpn']")
    if link.count() == 0:
        pytest.skip("Sidebar vpn link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "vpn" in page.url


def test_sidebar_link_shows_vpn_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='vpn']")
    if link.count() == 0:
        pytest.skip("Sidebar vpn link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#panel-vpn")).to_be_visible(timeout=5_000)


def test_sidebar_vpn_link_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='vpn']")
    if link.count() == 0:
        pytest.skip("Sidebar vpn link not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "active" in (link.first.get_attribute("class") or "")


# ── empty state ───────────────────────────────────────────────────────────────

def test_vpn_empty_state_no_js_error(logged_in: Page):
    page = logged_in
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    _go_vpn(page)
    page.wait_for_load_state("networkidle")
    assert [e for e in errors if "Uncaught" in e or "TypeError" in e] == []


# ── Webhook → UI integration ──────────────────────────────────────────────────

def test_webhook_vpn_tunnel_created_appears_in_table(logged_in: Page, api):
    page = logged_in
    _go_vpn(page)
    page.wait_for_load_state("networkidle")

    info = _seed_vpn_tunnel(api)
    page.reload()
    page.wait_for_load_state("networkidle")

    expect(
        page.locator("#vpnBody").get_by_text(info["name"]).first
    ).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/vpn-tunnels/{info['id']}")


def test_webhook_vpn_tunnel_deleted_removes_row(logged_in: Page, api):
    info = _seed_vpn_tunnel(api)
    page = logged_in
    _go_vpn(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#vpnBody").get_by_text(info["name"])
    expect(row.first).to_be_visible(timeout=8_000)

    api("POST", "/webhooks/nervum", {
        "event_type": "vpn_tunnel.deleted",
        "resource_type": "vpn_tunnel",
        "resource_id": info["id"],
        "payload": {},
    })
    page.reload()
    page.wait_for_load_state("networkidle")
    expect(row.first).to_be_hidden(timeout=8_000)


def test_webhook_vpn_tunnel_status_changed(api):
    """vpn_tunnel.status_changed updates status field in replica."""
    info = _seed_vpn_tunnel(api, status="build")
    api("POST", "/webhooks/nervum", {
        "event_type": "vpn_tunnel.status_changed",
        "resource_type": "vpn_tunnel",
        "resource_id": info["id"],
        "payload": {"id": info["id"], "name": info["name"], "status": "active"},
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/vpn-tunnels")
        tun = next((x for x in r["body"] if x["id"] == info["id"]), None)
        if tun and tun.get("status") == "active":
            break
        time.sleep(0.2)
    r = api("GET", "/api/sdn/vpn-tunnels")
    tun = next((x for x in r["body"] if x["id"] == info["id"]), None)
    assert tun is not None, "VPN tunnel not found after status_changed webhook"
    assert tun["status"] == "active"
    api("DELETE", f"/api/sdn/vpn-tunnels/{info['id']}")
