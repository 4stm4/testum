# SPDX-License-Identifier: MIT
"""E2E: SDN Gateway Bonds panel — Create form, API CRUD, table, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_GB_NAME = "e2e-gb-"


def _go_gwbond(page: Page):
    page.goto(f"{BASE_URL}/sdn#gwbond")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page):
    page.locator(
        "#panel-gwbond button:has-text('Create'), #panel-gwbond button:has-text('+ Create')"
    ).first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


def _seed_gateway_bond(api, name=None, **extra):
    rid = "e2e-gb-" + uuid.uuid4().hex[:10]
    rname = name or ("e2e-gb-" + uuid.uuid4().hex[:8])
    api("POST", "/webhooks/nervum", {
        "event_type": "gateway_bond.created",
        "resource_type": "gateway_bond",
        "resource_id": rid,
        "project_id": extra.get("project_id"),
        "payload": {"id": rid, "name": rname, "status": extra.get("status")},
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/gateway-bonds")
        if r["status"] == 200 and any(x["id"] == rid for x in r["body"]):
            break
        time.sleep(0.2)
    return {"id": rid, "name": rname}


# ── panel presence ────────────────────────────────────────────────────────────

def test_gwbond_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_gwbond(page)
    expect(page.locator("#panel-gwbond")).to_be_visible(timeout=8_000)


def test_gwbond_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_gwbond(page)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-routers")).to_be_hidden(timeout=5_000)


def test_gwbond_table_columns(logged_in: Page):
    page = logged_in
    _go_gwbond(page)
    headers = page.locator("#panel-gwbond thead th")
    texts = [headers.nth(i).inner_text().strip().upper() for i in range(headers.count())]
    assert any("NAME" in t for t in texts), f"NAME column missing: {texts}"
    assert any("MODE" in t for t in texts), f"MODE column missing: {texts}"


def test_gwbond_has_create_button(logged_in: Page):
    page = logged_in
    _go_gwbond(page)
    expect(page.locator(
        "#panel-gwbond button:has-text('Create'), #panel-gwbond button:has-text('+ Create')"
    ).first).to_be_visible(timeout=5_000)


# ── modal open / close ────────────────────────────────────────────────────────

def test_create_modal_opens(logged_in: Page):
    page = logged_in
    _go_gwbond(page)
    _open_create_modal(page)
    expect(page.locator("#createModal")).to_be_visible(timeout=5_000)


def test_create_modal_title_contains_bond(logged_in: Page):
    page = logged_in
    _go_gwbond(page)
    _open_create_modal(page)
    title = page.locator("#createModalTitle").inner_text()
    assert "bond" in title.lower(), f"Unexpected modal title: {title!r}"


def test_create_modal_has_name_field(logged_in: Page):
    page = logged_in
    _go_gwbond(page)
    _open_create_modal(page)
    expect(page.locator("#cf_name")).to_be_visible(timeout=3_000)


def test_create_modal_has_mode_field(logged_in: Page):
    page = logged_in
    _go_gwbond(page)
    _open_create_modal(page)
    expect(page.locator("#cf_mode")).to_be_visible(timeout=3_000)


def test_create_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_gwbond(page)
    _open_create_modal(page)
    page.locator("#createModal button:has-text('Cancel'), #createCancelBtn").first.click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


def test_create_modal_backdrop_click_closes(logged_in: Page):
    page = logged_in
    _go_gwbond(page)
    _open_create_modal(page)
    page.locator("#createModal").click(position={"x": 5, "y": 5})
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


# ── client-side validation ────────────────────────────────────────────────────

def test_create_empty_name_keeps_modal_open(logged_in: Page):
    page = logged_in
    _go_gwbond(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill("")
    page.locator("#createSubmitBtn").click()
    expect(page.locator("#createModal")).to_be_visible(timeout=3_000)


# ── successful create ─────────────────────────────────────────────────────────

def test_create_gwbond_name_only(logged_in: Page, api):
    name = _GB_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_gwbond(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/gateway-bonds" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201), f"Create failed: {resp.value.status}"
    gb_id = resp.value.json().get("id")
    if gb_id:
        api("DELETE", f"/api/sdn/gateway-bonds/{gb_id}")


def test_create_gwbond_with_mode_lacp(logged_in: Page, api):
    name = _GB_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_gwbond(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    page.locator("#cf_mode").fill("lacp")

    with page.expect_response(
        lambda r: "/api/sdn/gateway-bonds" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    gb_id = resp.value.json().get("id")
    if gb_id:
        r2 = api("GET", "/api/sdn/gateway-bonds")
        rec = next((x for x in r2["body"] if x["id"] == gb_id), None)
        assert rec and rec.get("mode") == "lacp", f"mode not 'lacp': {rec}"
        api("DELETE", f"/api/sdn/gateway-bonds/{gb_id}")


def test_create_gwbond_with_mode_active_backup(logged_in: Page, api):
    name = _GB_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_gwbond(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    page.locator("#cf_mode").fill("active_backup")

    with page.expect_response(
        lambda r: "/api/sdn/gateway-bonds" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    gb_id = resp.value.json().get("id")
    if gb_id:
        r2 = api("GET", "/api/sdn/gateway-bonds")
        rec = next((x for x in r2["body"] if x["id"] == gb_id), None)
        assert rec and rec.get("mode") == "active_backup", f"mode not 'active_backup': {rec}"
        api("DELETE", f"/api/sdn/gateway-bonds/{gb_id}")


# ── table update after create ─────────────────────────────────────────────────

def test_created_gwbond_appears_in_table(logged_in: Page, api):
    name = _GB_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_gwbond(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/gateway-bonds" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    gb_id = resp.value.json().get("id")

    row = page.locator("#gwbondBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    if gb_id:
        api("DELETE", f"/api/sdn/gateway-bonds/{gb_id}")


# ── delete from UI ────────────────────────────────────────────────────────────

def test_delete_gwbond_from_table(logged_in: Page, api):
    name = _GB_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/gateway-bonds", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create gateway bond via API")
    gb_id = r["body"]["id"]

    page = logged_in
    _go_gwbond(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#gwbondBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#gwbondBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/gateway-bonds")
    assert gb_id not in [x["id"] for x in r2["body"]]


# ── full roundtrip ────────────────────────────────────────────────────────────

def test_create_and_delete_full_roundtrip(logged_in: Page):
    name = _GB_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_gwbond(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/gateway-bonds" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)

    row = page.locator("#gwbondBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#gwbondBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_api_list_returns_list(api):
    r = api("GET", "/api/sdn/gateway-bonds")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_create_minimal(api):
    name = _GB_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/gateway-bonds", {"name": name})
    assert r["status"] in (200, 201), f"Expected 201, got {r}"
    assert r["body"].get("id")
    api("DELETE", f"/api/sdn/gateway-bonds/{r['body']['id']}")


def test_api_create_missing_name_returns_422(api):
    r = api("POST", "/api/sdn/gateway-bonds", {"project_id": "proj-abc"})
    assert r["status"] == 422, f"Expected 422, got {r}"


def test_api_delete_gwbond(api):
    r = api("POST", "/api/sdn/gateway-bonds", {"name": _GB_NAME + uuid.uuid4().hex[:8]})
    assert r["status"] in (200, 201)
    gb_id = r["body"]["id"]
    r2 = api("DELETE", f"/api/sdn/gateway-bonds/{gb_id}")
    assert r2["status"] in (200, 204)
    r3 = api("GET", "/api/sdn/gateway-bonds")
    assert gb_id not in [x["id"] for x in r3["body"]]


def test_api_delete_not_found(api):
    r = api("DELETE", "/api/sdn/gateway-bonds/nonexistent-e2e-gb")
    assert r["status"] == 404, f"Expected 404, got {r}"


def test_api_filter_by_project_id(api):
    pid = "proj-gb-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/gateway-bonds", {"name": _GB_NAME + uuid.uuid4().hex[:8], "project_id": pid})
    assert r["status"] in (200, 201)
    gb_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/gateway-bonds?project_id={pid}")
    assert r2["status"] == 200
    ids = [x["id"] for x in r2["body"]]
    assert gb_id in ids
    for x in r2["body"]:
        assert x["project_id"] == pid
    api("DELETE", f"/api/sdn/gateway-bonds/{gb_id}")


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_sidebar_link_activates_gwbond_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='gwbond']")
    if link.count() == 0:
        pytest.skip("Sidebar gwbond link not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "gwbond" in page.url, f"Expected 'gwbond' in URL, got: {page.url}"


def test_sidebar_link_shows_gwbond_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='gwbond']")
    if link.count() == 0:
        pytest.skip("Sidebar gwbond link not found")
    link.first.click()
    expect(page.locator("#panel-gwbond")).to_be_visible(timeout=5_000)


def test_sidebar_gwbond_link_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='gwbond']")
    if link.count() == 0:
        pytest.skip("Sidebar gwbond link not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "active" in (link.first.get_attribute("class") or "")


# ── no JS errors ──────────────────────────────────────────────────────────────

def test_no_js_errors_on_gwbond_panel(logged_in: Page):
    page = logged_in
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    _go_gwbond(page)
    page.wait_for_load_state("networkidle")
    assert [e for e in errors if "Uncaught" in e or "TypeError" in e] == []


# ── Webhook → integration ─────────────────────────────────────────────────────

def test_webhook_gwbond_created(logged_in: Page, api):
    page = logged_in
    _go_gwbond(page)
    page.wait_for_load_state("networkidle")

    info = _seed_gateway_bond(api)
    page.reload()
    page.wait_for_load_state("networkidle")

    expect(page.locator("#gwbondBody").get_by_text(info["name"]).first).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/gateway-bonds/{info['id']}")


def test_webhook_gwbond_deleted(logged_in: Page, api):
    info = _seed_gateway_bond(api)
    page = logged_in
    _go_gwbond(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#gwbondBody").get_by_text(info["name"])
    expect(row.first).to_be_visible(timeout=8_000)

    api("POST", "/webhooks/nervum", {
        "event_type": "gateway_bond.deleted",
        "resource_type": "gateway_bond",
        "resource_id": info["id"],
        "payload": {},
    })
    page.reload()
    page.wait_for_load_state("networkidle")
    expect(row.first).to_be_hidden(timeout=8_000)


def test_webhook_gwbond_updated(api):
    """gateway_bond.updated event updates the replica record."""
    info = _seed_gateway_bond(api)
    new_name = "e2e-gb-upd-" + uuid.uuid4().hex[:6]
    api("POST", "/webhooks/nervum", {
        "event_type": "gateway_bond.updated",
        "resource_type": "gateway_bond",
        "resource_id": info["id"],
        "payload": {"id": info["id"], "name": new_name},
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/gateway-bonds")
        rec = next((x for x in r["body"] if x["id"] == info["id"]), None)
        if rec and rec.get("name") == new_name:
            break
        time.sleep(0.2)
    r = api("GET", "/api/sdn/gateway-bonds")
    rec = next((x for x in r["body"] if x["id"] == info["id"]), None)
    assert rec is not None, "Record disappeared after update"
    assert rec["name"] == new_name, f"Name not updated: {rec}"
    api("DELETE", f"/api/sdn/gateway-bonds/{info['id']}")
