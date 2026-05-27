# SPDX-License-Identifier: MIT
"""E2E: SDN Routers panel — Create form, API CRUD, table, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_ROUTER_NAME = "e2e-router-"


def _go_routers(page: Page):
    page.goto(f"{BASE_URL}/sdn#routers")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page):
    page.locator("#panel-routers button:has-text('Create'), #panel-routers button:has-text('+ Create')").first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


def _seed_router(api, name: str | None = None, **extra) -> dict:
    """Seed a router via webhook. Polls until it lands in DB."""
    router_id   = "e2e-rtr-" + uuid.uuid4().hex[:10]
    router_name = name or (_ROUTER_NAME + uuid.uuid4().hex[:8])
    payload = {
        "event_type":    "router.created",
        "resource_type": "router",
        "resource_id":   router_id,
        "project_id":    extra.get("project_id"),
        "payload": {
            "id":         router_id,
            "name":       router_name,
            "project_id": extra.get("project_id"),
            "status":     extra.get("status", "active"),
            "mode":       extra.get("mode"),
        },
    }
    api("POST", "/webhooks/nervum", payload)
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/routers")
        if r["status"] == 200 and any(x["id"] == router_id for x in r["body"]):
            break
        time.sleep(0.2)
    return {"id": router_id, "name": router_name}


# ── panel presence ────────────────────────────────────────────────────────────

def test_routers_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_routers(page)
    expect(page.locator("#panel-routers")).to_be_visible(timeout=8_000)


def test_routers_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_routers(page)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-ports")).to_be_hidden(timeout=5_000)


def test_routers_table_columns(logged_in: Page):
    page = logged_in
    _go_routers(page)
    headers = page.locator("#panel-routers thead th")
    texts = [headers.nth(i).inner_text().strip().upper() for i in range(headers.count())]
    for col in ("NAME", "STATUS", "MODE"):
        assert any(col in t for t in texts), f"Column '{col}' not found in {texts}"


def test_routers_has_create_button(logged_in: Page):
    page = logged_in
    _go_routers(page)
    expect(page.locator(
        "#panel-routers button:has-text('Create'), #panel-routers button:has-text('+ Create')"
    ).first).to_be_visible(timeout=5_000)


# ── modal open / close ────────────────────────────────────────────────────────

def test_create_modal_opens(logged_in: Page):
    page = logged_in
    _go_routers(page)
    _open_create_modal(page)
    expect(page.locator("#createModal")).to_be_visible(timeout=5_000)


def test_create_modal_title(logged_in: Page):
    page = logged_in
    _go_routers(page)
    _open_create_modal(page)
    title = page.locator("#createModalTitle").inner_text()
    assert "router" in title.lower()


def test_create_modal_has_name_field(logged_in: Page):
    page = logged_in
    _go_routers(page)
    _open_create_modal(page)
    expect(page.locator("#cf_name")).to_be_visible(timeout=3_000)


def test_create_modal_has_mode_field(logged_in: Page):
    page = logged_in
    _go_routers(page)
    _open_create_modal(page)
    expect(page.locator("#cf_mode")).to_be_visible(timeout=3_000)


def test_create_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_routers(page)
    _open_create_modal(page)
    page.locator("#createModal button:has-text('Cancel'), #createCancelBtn").first.click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


def test_create_modal_backdrop_click_closes(logged_in: Page):
    page = logged_in
    _go_routers(page)
    _open_create_modal(page)
    page.locator("#createModal").click(position={"x": 5, "y": 5})
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


# ── client-side validation ────────────────────────────────────────────────────

def test_create_empty_name_keeps_modal_open(logged_in: Page):
    page = logged_in
    _go_routers(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill("")
    page.locator("#createSubmitBtn").click()
    expect(page.locator("#createModal")).to_be_visible(timeout=3_000)


def test_create_empty_name_no_api_call(logged_in: Page):
    page = logged_in
    _go_routers(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill("")
    calls: list[str] = []
    page.on("request", lambda req: calls.append(req.url) if "/api/sdn/routers" in req.url and req.method == "POST" else None)
    page.locator("#createSubmitBtn").click()
    page.wait_for_timeout(500)
    assert calls == [], "POST should not fire with empty name"


# ── successful create ─────────────────────────────────────────────────────────

def test_create_router_name_only(logged_in: Page, api):
    name = _ROUTER_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_routers(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/routers" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    router_id = resp.value.json().get("id")
    if router_id:
        api("DELETE", f"/api/sdn/routers/{router_id}")


def test_create_router_with_mode(logged_in: Page, api):
    name = _ROUTER_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_routers(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    page.locator("#cf_mode").fill("slaac")

    with page.expect_response(
        lambda r: "/api/sdn/routers" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    router_id = resp.value.json().get("id")
    if router_id:
        r2 = api("GET", "/api/sdn/routers")
        router = next((x for x in r2["body"] if x["id"] == router_id), None)
        assert router and router["mode"] == "slaac"
        api("DELETE", f"/api/sdn/routers/{router_id}")


def test_create_router_status_build(api):
    """Newly created router has status 'build'."""
    name = _ROUTER_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/routers", {"name": name})
    assert r["status"] in (200, 201)
    router_id = r["body"]["id"]
    r2 = api("GET", "/api/sdn/routers")
    router = next((x for x in r2["body"] if x["id"] == router_id), None)
    assert router and router["status"] == "build"
    api("DELETE", f"/api/sdn/routers/{router_id}")


# ── table update after create ─────────────────────────────────────────────────

def test_created_router_appears_in_table(logged_in: Page, api):
    name = _ROUTER_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_routers(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/routers" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    router_id = resp.value.json().get("id")

    row = page.locator("#routersBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    if router_id:
        api("DELETE", f"/api/sdn/routers/{router_id}")


# ── delete from UI ────────────────────────────────────────────────────────────

def test_delete_router_from_table(logged_in: Page, api):
    name = _ROUTER_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/routers", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create router via API")
    router_id = r["body"]["id"]

    page = logged_in
    _go_routers(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#routersBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#routersBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/routers")
    assert router_id not in [x["id"] for x in r2["body"]]


# ── full roundtrip ────────────────────────────────────────────────────────────

def test_create_and_delete_full_roundtrip(logged_in: Page):
    name = _ROUTER_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_routers(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/routers" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)

    row = page.locator("#routersBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#routersBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_api_list_returns_list(api):
    r = api("GET", "/api/sdn/routers")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_create_minimal(api):
    name = _ROUTER_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/routers", {"name": name})
    assert r["status"] in (200, 201)
    assert r["body"].get("id")
    api("DELETE", f"/api/sdn/routers/{r['body']['id']}")


def test_api_create_all_fields(api):
    name = _ROUTER_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/routers", {
        "name": name, "project_id": "proj-e2e", "mode": "stateful",
    })
    assert r["status"] in (200, 201)
    router_id = r["body"]["id"]
    r2 = api("GET", "/api/sdn/routers")
    router = next((x for x in r2["body"] if x["id"] == router_id), None)
    assert router["project_id"] == "proj-e2e"
    assert router["mode"] == "stateful"
    api("DELETE", f"/api/sdn/routers/{router_id}")


def test_api_create_missing_name_returns_422(api):
    r = api("POST", "/api/sdn/routers", {"project_id": "proj-abc"})
    assert r["status"] == 422


def test_api_delete_router(api):
    r = api("POST", "/api/sdn/routers", {"name": _ROUTER_NAME + uuid.uuid4().hex[:8]})
    router_id = r["body"]["id"]
    r2 = api("DELETE", f"/api/sdn/routers/{router_id}")
    assert r2["status"] in (200, 204)
    r3 = api("GET", "/api/sdn/routers")
    assert router_id not in [x["id"] for x in r3["body"]]


def test_api_delete_not_found(api):
    r = api("DELETE", "/api/sdn/routers/nonexistent-e2e-router")
    assert r["status"] == 404


def test_api_filter_by_project_id(api):
    pid = "proj-rtr-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/routers", {"name": _ROUTER_NAME + uuid.uuid4().hex[:8], "project_id": pid})
    router_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/routers?project_id={pid}")
    assert r2["status"] == 200
    ids = [x["id"] for x in r2["body"]]
    assert router_id in ids
    for x in r2["body"]:
        assert x["project_id"] == pid
    api("DELETE", f"/api/sdn/routers/{router_id}")


def test_api_mode_values(api):
    """All four IPv6 mode values are accepted."""
    for mode in ("off", "slaac", "stateful", "stateless"):
        r = api("POST", "/api/sdn/routers", {
            "name": _ROUTER_NAME + uuid.uuid4().hex[:8], "mode": mode,
        })
        assert r["status"] in (200, 201), f"mode={mode} rejected"
        api("DELETE", f"/api/sdn/routers/{r['body']['id']}")


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_sidebar_link_activates_routers_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='routers']")
    if link.count() == 0:
        pytest.skip("Sidebar routers link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "routers" in page.url


def test_sidebar_link_shows_routers_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='routers']")
    if link.count() == 0:
        pytest.skip("Sidebar routers link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#panel-routers")).to_be_visible(timeout=5_000)


def test_sidebar_routers_link_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='routers']")
    if link.count() == 0:
        pytest.skip("Sidebar routers link not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "active" in (link.first.get_attribute("class") or "")


# ── empty state ───────────────────────────────────────────────────────────────

def test_routers_empty_state_no_js_error(logged_in: Page):
    page = logged_in
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    _go_routers(page)
    page.wait_for_load_state("networkidle")
    assert [e for e in errors if "Uncaught" in e or "TypeError" in e] == []


# ── Webhook → UI integration ──────────────────────────────────────────────────

def test_webhook_router_created_appears_in_table(logged_in: Page, api):
    page = logged_in
    _go_routers(page)
    page.wait_for_load_state("networkidle")

    info = _seed_router(api)
    page.reload()
    page.wait_for_load_state("networkidle")

    expect(page.locator("#routersBody").get_by_text(info["name"]).first).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/routers/{info['id']}")


def test_webhook_router_deleted_removes_row(logged_in: Page, api):
    info = _seed_router(api)
    page = logged_in
    _go_routers(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#routersBody").get_by_text(info["name"])
    expect(row.first).to_be_visible(timeout=8_000)

    api("POST", "/webhooks/nervum", {
        "event_type":    "router.deleted",
        "resource_type": "router",
        "resource_id":   info["id"],
        "payload":       {},
    })
    page.reload()
    page.wait_for_load_state("networkidle")
    expect(row.first).to_be_hidden(timeout=8_000)


def test_webhook_router_status_changed(api):
    """router.status_changed updates status in replica."""
    info = _seed_router(api, status="build")
    api("POST", "/webhooks/nervum", {
        "event_type":    "router.status_changed",
        "resource_type": "router",
        "resource_id":   info["id"],
        "payload":       {"id": info["id"], "name": info["name"], "status": "active"},
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/routers")
        rtr = next((x for x in r["body"] if x["id"] == info["id"]), None)
        if rtr and rtr["status"] == "active":
            break
        time.sleep(0.2)
    r = api("GET", "/api/sdn/routers")
    rtr = next((x for x in r["body"] if x["id"] == info["id"]), None)
    assert rtr and rtr["status"] == "active"
    api("DELETE", f"/api/sdn/routers/{info['id']}")
