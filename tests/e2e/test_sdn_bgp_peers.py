# SPDX-License-Identifier: MIT
"""E2E: SDN BGP Peers panel — Create form, API CRUD, table, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_bgp(page: Page):
    page.goto(f"{BASE_URL}/sdn#bgp")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page):
    page.locator(
        "#panel-bgp button:has-text('Create'), #panel-bgp button:has-text('+ Create')"
    ).first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


def _unique_ip() -> str:
    """Return a unique 10.99.x.x IP."""
    a = uuid.uuid4().int & 0xFF
    b = uuid.uuid4().int & 0xFF
    return f"10.99.{a}.{b}"


def _seed_bgp(api, peer_ip: str | None = None, **extra) -> dict:
    """Seed a BGP peer via webhook. Polls until it lands in DB."""
    bgp_id = "e2e-bgp-" + uuid.uuid4().hex[:10]
    ip = peer_ip or _unique_ip()
    payload = {
        "event_type": "bgp_peer.created",
        "resource_type": "bgp_peer",
        "resource_id": bgp_id,
        "project_id": extra.get("project_id"),
        "payload": {
            "id": bgp_id,
            "peer_ip": ip,
            "remote_asn": extra.get("remote_asn"),
            "router_id": extra.get("router_id"),
            "project_id": extra.get("project_id"),
        },
    }
    api("POST", "/webhooks/nervum", payload)
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/bgp-peers")
        if r["status"] == 200 and any(x["id"] == bgp_id for x in r["body"]):
            break
        time.sleep(0.2)
    return {"id": bgp_id, "peer_ip": ip}


# ── panel presence ────────────────────────────────────────────────────────────

def test_bgp_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_bgp(page)
    expect(page.locator("#panel-bgp")).to_be_visible(timeout=8_000)


def test_bgp_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_bgp(page)
    expect(page.locator("#panel-routers")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)


def test_bgp_table_columns(logged_in: Page):
    page = logged_in
    _go_bgp(page)
    headers = page.locator("#panel-bgp thead th")
    texts = [headers.nth(i).inner_text().strip().upper() for i in range(headers.count())]
    for col in ("PEER IP", "REMOTE ASN"):
        assert any(col in t for t in texts), f"Column '{col}' not found in {texts}"


def test_bgp_has_create_button(logged_in: Page):
    page = logged_in
    _go_bgp(page)
    expect(
        page.locator(
            "#panel-bgp button:has-text('Create'), #panel-bgp button:has-text('+ Create')"
        ).first
    ).to_be_visible(timeout=5_000)


# ── modal open / close ────────────────────────────────────────────────────────

def test_create_modal_opens(logged_in: Page):
    page = logged_in
    _go_bgp(page)
    _open_create_modal(page)
    expect(page.locator("#createModal")).to_be_visible(timeout=5_000)


def test_create_modal_title_contains_bgp(logged_in: Page):
    page = logged_in
    _go_bgp(page)
    _open_create_modal(page)
    title = page.locator("#createModalTitle").inner_text()
    assert "bgp" in title.lower(), f"Modal title '{title}' does not mention bgp"


def test_create_modal_has_peer_ip_field(logged_in: Page):
    page = logged_in
    _go_bgp(page)
    _open_create_modal(page)
    expect(page.locator("#cf_peer_ip")).to_be_visible(timeout=3_000)


def test_create_modal_has_remote_asn_field(logged_in: Page):
    page = logged_in
    _go_bgp(page)
    _open_create_modal(page)
    expect(page.locator("#cf_remote_asn")).to_be_visible(timeout=3_000)


def test_create_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_bgp(page)
    _open_create_modal(page)
    page.locator("#createCancelBtn").click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


def test_create_empty_peer_ip_keeps_modal_open(logged_in: Page):
    page = logged_in
    _go_bgp(page)
    _open_create_modal(page)
    page.locator("#cf_peer_ip").fill("")
    page.locator("#createSubmitBtn").click()
    expect(page.locator("#createModal")).to_be_visible(timeout=3_000)


# ── successful create ─────────────────────────────────────────────────────────

def test_create_bgp_peer_ip_only(logged_in: Page, api):
    ip = _unique_ip()
    page = logged_in
    _go_bgp(page)
    _open_create_modal(page)
    page.locator("#cf_peer_ip").fill(ip)

    with page.expect_response(
        lambda r: "/api/sdn/bgp-peers" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    peer_id = resp.value.json().get("id")
    if peer_id:
        api("DELETE", f"/api/sdn/bgp-peers/{peer_id}")


def test_create_bgp_with_all_fields(logged_in: Page, api):
    ip = _unique_ip()
    router_id = "rtr-e2e-" + uuid.uuid4().hex[:8]
    page = logged_in
    _go_bgp(page)
    _open_create_modal(page)
    page.locator("#cf_peer_ip").fill(ip)
    page.locator("#cf_remote_asn").fill("65001")
    page.locator("#cf_router_id").fill(router_id)

    with page.expect_response(
        lambda r: "/api/sdn/bgp-peers" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    peer_id = resp.value.json().get("id")
    if peer_id:
        r2 = api("GET", "/api/sdn/bgp-peers")
        peer = next((x for x in r2["body"] if x["id"] == peer_id), None)
        assert peer is not None
        assert str(peer["remote_asn"]) == "65001"
        api("DELETE", f"/api/sdn/bgp-peers/{peer_id}")


def test_remote_asn_is_number_in_api_response(api):
    ip = _unique_ip()
    r = api("POST", "/api/sdn/bgp-peers", {"peer_ip": ip, "remote_asn": 65002})
    assert r["status"] in (200, 201)
    peer_id = r["body"]["id"]
    r2 = api("GET", "/api/sdn/bgp-peers")
    peer = next((x for x in r2["body"] if x["id"] == peer_id), None)
    assert peer is not None
    assert isinstance(peer["remote_asn"], (int, float)), (
        f"remote_asn should be a number, got {type(peer['remote_asn'])}"
    )
    api("DELETE", f"/api/sdn/bgp-peers/{peer_id}")


def test_created_peer_ip_appears_in_table(logged_in: Page, api):
    ip = _unique_ip()
    page = logged_in
    _go_bgp(page)
    _open_create_modal(page)
    page.locator("#cf_peer_ip").fill(ip)

    with page.expect_response(
        lambda r: "/api/sdn/bgp-peers" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    peer_id = resp.value.json().get("id")

    row = page.locator("#bgpBody").get_by_text(ip)
    expect(row.first).to_be_visible(timeout=8_000)
    if peer_id:
        api("DELETE", f"/api/sdn/bgp-peers/{peer_id}")


# ── delete from UI ────────────────────────────────────────────────────────────

def test_delete_bgp_peer_from_table(logged_in: Page, api):
    ip = _unique_ip()
    r = api("POST", "/api/sdn/bgp-peers", {"peer_ip": ip})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create BGP peer via API")
    peer_id = r["body"]["id"]

    page = logged_in
    _go_bgp(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#bgpBody").get_by_text(ip)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#bgpBody tr:has-text('{ip}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/bgp-peers")
    assert peer_id not in [x["id"] for x in r2["body"]]


# ── full roundtrip ────────────────────────────────────────────────────────────

def test_create_and_delete_full_roundtrip(logged_in: Page):
    ip = _unique_ip()
    page = logged_in
    _go_bgp(page)
    _open_create_modal(page)
    page.locator("#cf_peer_ip").fill(ip)

    with page.expect_response(
        lambda r: "/api/sdn/bgp-peers" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)

    row = page.locator("#bgpBody").get_by_text(ip)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#bgpBody tr:has-text('{ip}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_api_list_returns_list(api):
    r = api("GET", "/api/sdn/bgp-peers")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_create_minimal(api):
    ip = _unique_ip()
    r = api("POST", "/api/sdn/bgp-peers", {"peer_ip": ip})
    assert r["status"] in (200, 201)
    assert r["body"].get("id")
    api("DELETE", f"/api/sdn/bgp-peers/{r['body']['id']}")


def test_api_create_missing_peer_ip_returns_422(api):
    r = api("POST", "/api/sdn/bgp-peers", {"remote_asn": 65000})
    assert r["status"] == 422


def test_api_delete_bgp_peer(api):
    ip = _unique_ip()
    r = api("POST", "/api/sdn/bgp-peers", {"peer_ip": ip})
    peer_id = r["body"]["id"]
    r2 = api("DELETE", f"/api/sdn/bgp-peers/{peer_id}")
    assert r2["status"] in (200, 204)
    r3 = api("GET", "/api/sdn/bgp-peers")
    assert peer_id not in [x["id"] for x in r3["body"]]


def test_api_delete_not_found(api):
    r = api("DELETE", "/api/sdn/bgp-peers/nonexistent-e2e-bgp")
    assert r["status"] == 404


def test_api_filter_by_project_id(api):
    pid = "proj-bgp-" + uuid.uuid4().hex[:6]
    ip = _unique_ip()
    r = api("POST", "/api/sdn/bgp-peers", {"peer_ip": ip, "project_id": pid})
    peer_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/bgp-peers?project_id={pid}")
    assert r2["status"] == 200
    ids = [x["id"] for x in r2["body"]]
    assert peer_id in ids
    for x in r2["body"]:
        assert x["project_id"] == pid
    api("DELETE", f"/api/sdn/bgp-peers/{peer_id}")


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_sidebar_link_activates_bgp_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='bgp']")
    if link.count() == 0:
        pytest.skip("Sidebar bgp link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "bgp" in page.url


def test_sidebar_link_shows_bgp_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='bgp']")
    if link.count() == 0:
        pytest.skip("Sidebar bgp link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#panel-bgp")).to_be_visible(timeout=5_000)


def test_sidebar_bgp_link_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='bgp']")
    if link.count() == 0:
        pytest.skip("Sidebar bgp link not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "active" in (link.first.get_attribute("class") or "")


# ── no JS errors ──────────────────────────────────────────────────────────────

def test_bgp_no_js_errors(logged_in: Page):
    page = logged_in
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    _go_bgp(page)
    page.wait_for_load_state("networkidle")
    assert [e for e in errors if "Uncaught" in e or "TypeError" in e] == []


# ── Webhook → UI integration ──────────────────────────────────────────────────

def test_webhook_bgp_created_appears_in_table(logged_in: Page, api):
    page = logged_in
    _go_bgp(page)
    page.wait_for_load_state("networkidle")

    info = _seed_bgp(api)
    page.reload()
    page.wait_for_load_state("networkidle")

    expect(
        page.locator("#bgpBody").get_by_text(info["peer_ip"]).first
    ).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/bgp-peers/{info['id']}")


def test_webhook_bgp_deleted_removes_row(logged_in: Page, api):
    info = _seed_bgp(api)
    page = logged_in
    _go_bgp(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#bgpBody").get_by_text(info["peer_ip"])
    expect(row.first).to_be_visible(timeout=8_000)

    api("POST", "/webhooks/nervum", {
        "event_type": "bgp_peer.deleted",
        "resource_type": "bgp_peer",
        "resource_id": info["id"],
        "payload": {},
    })
    page.reload()
    page.wait_for_load_state("networkidle")
    expect(row.first).to_be_hidden(timeout=8_000)


def test_webhook_bgp_updated(api):
    """bgp_peer.updated reflects changed remote_asn in replica."""
    info = _seed_bgp(api, remote_asn=64512)
    new_asn = 64999
    api("POST", "/webhooks/nervum", {
        "event_type": "bgp_peer.updated",
        "resource_type": "bgp_peer",
        "resource_id": info["id"],
        "payload": {
            "id": info["id"],
            "peer_ip": info["peer_ip"],
            "remote_asn": new_asn,
        },
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/bgp-peers")
        peer = next((x for x in r["body"] if x["id"] == info["id"]), None)
        if peer and peer.get("remote_asn") == new_asn:
            break
        time.sleep(0.2)
    r = api("GET", "/api/sdn/bgp-peers")
    peer = next((x for x in r["body"] if x["id"] == info["id"]), None)
    assert peer and peer.get("remote_asn") == new_asn
    api("DELETE", f"/api/sdn/bgp-peers/{info['id']}")
