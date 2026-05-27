# SPDX-License-Identifier: MIT
"""E2E: SDN Floating IPs panel — Create form, API CRUD, table, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_FIP_PREFIX = "10.200."


def _go_fips(page: Page):
    page.goto(f"{BASE_URL}/sdn#fips")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page):
    page.locator(
        "#panel-fips button:has-text('Create'), #panel-fips button:has-text('+ Create')"
    ).first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


def _rand_ip() -> str:
    a = uuid.uuid4().int % 254 + 1
    b = uuid.uuid4().int % 254 + 1
    return f"10.200.{a}.{b}"


def _seed_fip(api, address: str | None = None, **extra) -> dict:
    """Seed a floating IP via webhook. Polls until it lands in DB."""
    fip_id = "e2e-fip-" + uuid.uuid4().hex[:10]
    fip_address = address or _rand_ip()
    payload = {
        "event_type": "floating_ip.created",
        "resource_type": "floating_ip",
        "resource_id": fip_id,
        "project_id": extra.get("project_id"),
        "payload": {
            "id": fip_id,
            "address": fip_address,
            "project_id": extra.get("project_id"),
            "router_id": extra.get("router_id"),
            "status": extra.get("status", "down"),
        },
    }
    api("POST", "/webhooks/nervum", payload)
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/floating-ips")
        if r["status"] == 200 and any(x["id"] == fip_id for x in r["body"]):
            break
        time.sleep(0.2)
    return {"id": fip_id, "address": fip_address}


# ── panel presence ────────────────────────────────────────────────────────────

def test_fips_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_fips(page)
    expect(page.locator("#panel-fips")).to_be_visible(timeout=8_000)


def test_fips_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_fips(page)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-routers")).to_be_hidden(timeout=5_000)


def test_fips_table_columns(logged_in: Page):
    page = logged_in
    _go_fips(page)
    headers = page.locator("#panel-fips thead th")
    texts = [headers.nth(i).inner_text().strip().upper() for i in range(headers.count())]
    for col in ("ADDRESS", "STATUS"):
        assert any(col in t for t in texts), f"Column '{col}' not found in {texts}"


def test_fips_has_create_button(logged_in: Page):
    page = logged_in
    _go_fips(page)
    expect(
        page.locator(
            "#panel-fips button:has-text('Create'), #panel-fips button:has-text('+ Create')"
        ).first
    ).to_be_visible(timeout=5_000)


# ── modal open / close ────────────────────────────────────────────────────────

def test_create_modal_opens(logged_in: Page):
    page = logged_in
    _go_fips(page)
    _open_create_modal(page)
    expect(page.locator("#createModal")).to_be_visible(timeout=5_000)


def test_create_modal_has_address_field(logged_in: Page):
    page = logged_in
    _go_fips(page)
    _open_create_modal(page)
    expect(page.locator("#cf_address")).to_be_visible(timeout=3_000)


def test_create_modal_has_router_id_field(logged_in: Page):
    page = logged_in
    _go_fips(page)
    _open_create_modal(page)
    expect(page.locator("#cf_router_id")).to_be_visible(timeout=3_000)


def test_create_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_fips(page)
    _open_create_modal(page)
    page.locator(
        "#createModal button:has-text('Cancel'), #createCancelBtn"
    ).first.click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


# ── successful create ─────────────────────────────────────────────────────────

def test_create_fip_with_address(logged_in: Page, api):
    address = _rand_ip()
    page = logged_in
    _go_fips(page)
    _open_create_modal(page)
    page.locator("#cf_address").fill(address)

    with page.expect_response(
        lambda r: "/api/sdn/floating-ips" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    fip_id = resp.value.json().get("id")
    if fip_id:
        api("DELETE", f"/api/sdn/floating-ips/{fip_id}")


def test_create_fip_with_all_fields(logged_in: Page, api):
    address = _rand_ip()
    router_id = "rtr-" + uuid.uuid4().hex[:8]
    pid = "proj-fip-" + uuid.uuid4().hex[:6]
    page = logged_in
    _go_fips(page)
    _open_create_modal(page)
    page.locator("#cf_address").fill(address)
    router_field = page.locator("#cf_router_id")
    if router_field.count() > 0:
        router_field.fill(router_id)
    proj_field = page.locator("#cf_project_id")
    if proj_field.count() > 0:
        proj_field.fill(pid)

    with page.expect_response(
        lambda r: "/api/sdn/floating-ips" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    fip_id = resp.value.json().get("id")
    if fip_id:
        api("DELETE", f"/api/sdn/floating-ips/{fip_id}")


def test_create_fip_empty_form_still_posts(logged_in: Page, api):
    """Floating IPs have no required fields — empty form should still POST."""
    page = logged_in
    _go_fips(page)
    _open_create_modal(page)

    with page.expect_response(
        lambda r: "/api/sdn/floating-ips" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    fip_id = resp.value.json().get("id")
    if fip_id:
        api("DELETE", f"/api/sdn/floating-ips/{fip_id}")


def test_fip_initial_status_is_down(api):
    """Newly created floating IP has status 'down'."""
    address = _rand_ip()
    r = api("POST", "/api/sdn/floating-ips", {"address": address})
    assert r["status"] in (200, 201)
    fip_id = r["body"]["id"]
    r2 = api("GET", "/api/sdn/floating-ips")
    fip = next((x for x in r2["body"] if x["id"] == fip_id), None)
    assert fip is not None
    assert fip["status"] == "down"
    api("DELETE", f"/api/sdn/floating-ips/{fip_id}")


def test_created_fip_appears_in_table(logged_in: Page, api):
    address = _rand_ip()
    page = logged_in
    _go_fips(page)
    _open_create_modal(page)
    page.locator("#cf_address").fill(address)

    with page.expect_response(
        lambda r: "/api/sdn/floating-ips" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    fip_id = resp.value.json().get("id")

    row = page.locator("#fipsBody").get_by_text(address)
    expect(row.first).to_be_visible(timeout=8_000)
    if fip_id:
        api("DELETE", f"/api/sdn/floating-ips/{fip_id}")


# ── delete from UI ────────────────────────────────────────────────────────────

def test_delete_fip_from_table(logged_in: Page, api):
    address = _rand_ip()
    r = api("POST", "/api/sdn/floating-ips", {"address": address})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create floating IP via API")
    fip_id = r["body"]["id"]

    page = logged_in
    _go_fips(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#fipsBody").get_by_text(address)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#fipsBody tr:has-text('{address}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/floating-ips")
    assert fip_id not in [x["id"] for x in r2["body"]]


# ── full roundtrip ────────────────────────────────────────────────────────────

def test_create_and_delete_full_roundtrip(logged_in: Page):
    address = _rand_ip()
    page = logged_in
    _go_fips(page)
    _open_create_modal(page)
    page.locator("#cf_address").fill(address)

    with page.expect_response(
        lambda r: "/api/sdn/floating-ips" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)

    row = page.locator("#fipsBody").get_by_text(address)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#fipsBody tr:has-text('{address}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_api_list_returns_list(api):
    r = api("GET", "/api/sdn/floating-ips")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_create_fip(api):
    address = _rand_ip()
    r = api("POST", "/api/sdn/floating-ips", {"address": address})
    assert r["status"] in (200, 201)
    assert r["body"].get("id")
    api("DELETE", f"/api/sdn/floating-ips/{r['body']['id']}")


def test_api_delete_fip(api):
    r = api("POST", "/api/sdn/floating-ips", {"address": _rand_ip()})
    assert r["status"] in (200, 201)
    fip_id = r["body"]["id"]
    r2 = api("DELETE", f"/api/sdn/floating-ips/{fip_id}")
    assert r2["status"] in (200, 204)
    r3 = api("GET", "/api/sdn/floating-ips")
    assert fip_id not in [x["id"] for x in r3["body"]]


def test_api_delete_fip_not_found(api):
    r = api("DELETE", "/api/sdn/floating-ips/nonexistent-e2e-fip")
    assert r["status"] == 404


def test_api_fip_project_filter(api):
    pid = "proj-fip-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/floating-ips", {
        "address": _rand_ip(),
        "project_id": pid,
    })
    assert r["status"] in (200, 201)
    fip_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/floating-ips?project_id={pid}")
    assert r2["status"] == 200
    ids = [x["id"] for x in r2["body"]]
    assert fip_id in ids
    for x in r2["body"]:
        assert x["project_id"] == pid
    api("DELETE", f"/api/sdn/floating-ips/{fip_id}")


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_sidebar_link_activates_fips_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='fips']")
    if link.count() == 0:
        pytest.skip("Sidebar fips link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "fips" in page.url


def test_sidebar_link_shows_fips_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='fips']")
    if link.count() == 0:
        pytest.skip("Sidebar fips link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#panel-fips")).to_be_visible(timeout=5_000)


def test_sidebar_fips_link_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='fips']")
    if link.count() == 0:
        pytest.skip("Sidebar fips link not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "active" in (link.first.get_attribute("class") or "")


# ── empty state ───────────────────────────────────────────────────────────────

def test_fips_empty_state_no_js_error(logged_in: Page):
    page = logged_in
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    _go_fips(page)
    page.wait_for_load_state("networkidle")
    assert [e for e in errors if "Uncaught" in e or "TypeError" in e] == []


# ── Webhook → UI integration ──────────────────────────────────────────────────

def test_webhook_fip_created_appears_in_table(logged_in: Page, api):
    page = logged_in
    _go_fips(page)
    page.wait_for_load_state("networkidle")

    info = _seed_fip(api)
    page.reload()
    page.wait_for_load_state("networkidle")

    expect(
        page.locator("#fipsBody").get_by_text(info["address"]).first
    ).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/floating-ips/{info['id']}")


def test_webhook_fip_deleted_removes_row(logged_in: Page, api):
    info = _seed_fip(api)
    page = logged_in
    _go_fips(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#fipsBody").get_by_text(info["address"])
    expect(row.first).to_be_visible(timeout=8_000)

    api("POST", "/webhooks/nervum", {
        "event_type": "floating_ip.deleted",
        "resource_type": "floating_ip",
        "resource_id": info["id"],
        "payload": {},
    })
    page.reload()
    page.wait_for_load_state("networkidle")
    expect(row.first).to_be_hidden(timeout=8_000)


def test_webhook_fip_status_changed(api):
    """floating_ip.status_changed updates status field in replica."""
    info = _seed_fip(api, status="down")
    api("POST", "/webhooks/nervum", {
        "event_type": "floating_ip.status_changed",
        "resource_type": "floating_ip",
        "resource_id": info["id"],
        "payload": {"id": info["id"], "address": info["address"], "status": "active"},
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/floating-ips")
        fip = next((x for x in r["body"] if x["id"] == info["id"]), None)
        if fip and fip.get("status") == "active":
            break
        time.sleep(0.2)
    r = api("GET", "/api/sdn/floating-ips")
    fip = next((x for x in r["body"] if x["id"] == info["id"]), None)
    assert fip is not None, "Floating IP not found after status_changed webhook"
    assert fip["status"] == "active"
    api("DELETE", f"/api/sdn/floating-ips/{info['id']}")
