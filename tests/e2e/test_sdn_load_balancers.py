# SPDX-License-Identifier: MIT
"""E2E: SDN Load Balancers panel — Create form, API CRUD, table, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_LB_NAME = "e2e-lb-"


def _go_lbs(page: Page):
    page.goto(f"{BASE_URL}/sdn#lbs")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page):
    page.locator(
        "#panel-lbs button:has-text('Create'), #panel-lbs button:has-text('+ Create')"
    ).first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


def _seed_lb(api, name: str | None = None, **extra) -> dict:
    """Seed a load balancer via webhook. Polls until it lands in DB."""
    lb_id = "e2e-lb-" + uuid.uuid4().hex[:10]
    lb_name = name or (_LB_NAME + uuid.uuid4().hex[:8])
    payload = {
        "event_type": "load_balancer.created",
        "resource_type": "load_balancer",
        "resource_id": lb_id,
        "project_id": extra.get("project_id"),
        "payload": {
            "id": lb_id,
            "name": lb_name,
            "project_id": extra.get("project_id"),
            "router_id": extra.get("router_id"),
            "status": extra.get("status", "build"),
        },
    }
    api("POST", "/webhooks/nervum", payload)
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/load-balancers")
        if r["status"] == 200 and any(x["id"] == lb_id for x in r["body"]):
            break
        time.sleep(0.2)
    return {"id": lb_id, "name": lb_name}


# ── panel presence ────────────────────────────────────────────────────────────

def test_lbs_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_lbs(page)
    expect(page.locator("#panel-lbs")).to_be_visible(timeout=8_000)


def test_lbs_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_lbs(page)
    expect(page.locator("#panel-routers")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)


def test_lbs_table_columns(logged_in: Page):
    page = logged_in
    _go_lbs(page)
    headers = page.locator("#panel-lbs thead th")
    texts = [headers.nth(i).inner_text().strip().upper() for i in range(headers.count())]
    for col in ("NAME", "STATUS"):
        assert any(col in t for t in texts), f"Column '{col}' not found in {texts}"


def test_lbs_has_create_button(logged_in: Page):
    page = logged_in
    _go_lbs(page)
    expect(
        page.locator(
            "#panel-lbs button:has-text('Create'), #panel-lbs button:has-text('+ Create')"
        ).first
    ).to_be_visible(timeout=5_000)


# ── modal open / close ────────────────────────────────────────────────────────

def test_create_modal_opens(logged_in: Page):
    page = logged_in
    _go_lbs(page)
    _open_create_modal(page)
    expect(page.locator("#createModal")).to_be_visible(timeout=5_000)


def test_create_modal_title_contains_lb_or_load(logged_in: Page):
    page = logged_in
    _go_lbs(page)
    _open_create_modal(page)
    title = page.locator("#createModalTitle").inner_text()
    assert "lb" in title.lower() or "load" in title.lower(), (
        f"Modal title '{title}' does not mention lb/load"
    )


def test_create_modal_has_name_field(logged_in: Page):
    page = logged_in
    _go_lbs(page)
    _open_create_modal(page)
    expect(page.locator("#cf_name")).to_be_visible(timeout=3_000)


def test_create_modal_has_router_id_field(logged_in: Page):
    page = logged_in
    _go_lbs(page)
    _open_create_modal(page)
    expect(page.locator("#cf_router_id")).to_be_visible(timeout=3_000)


def test_create_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_lbs(page)
    _open_create_modal(page)
    page.locator("#createCancelBtn").click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


def test_create_empty_name_keeps_modal_open(logged_in: Page):
    page = logged_in
    _go_lbs(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill("")
    page.locator("#createSubmitBtn").click()
    expect(page.locator("#createModal")).to_be_visible(timeout=3_000)


# ── successful create ─────────────────────────────────────────────────────────

def test_create_lb_name_only(logged_in: Page, api):
    name = _LB_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_lbs(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/load-balancers" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    lb_id = resp.value.json().get("id")
    if lb_id:
        api("DELETE", f"/api/sdn/load-balancers/{lb_id}")


def test_create_lb_with_router_id(logged_in: Page, api):
    name = _LB_NAME + uuid.uuid4().hex[:8]
    router_id = "rtr-e2e-" + uuid.uuid4().hex[:8]
    page = logged_in
    _go_lbs(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    page.locator("#cf_router_id").fill(router_id)

    with page.expect_response(
        lambda r: "/api/sdn/load-balancers" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    lb_id = resp.value.json().get("id")
    if lb_id:
        r2 = api("GET", "/api/sdn/load-balancers")
        lb = next((x for x in r2["body"] if x["id"] == lb_id), None)
        assert lb and lb["router_id"] == router_id
        api("DELETE", f"/api/sdn/load-balancers/{lb_id}")


def test_create_lb_initial_status_is_build(api):
    name = _LB_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/load-balancers", {"name": name})
    assert r["status"] in (200, 201)
    lb_id = r["body"]["id"]
    r2 = api("GET", "/api/sdn/load-balancers")
    lb = next((x for x in r2["body"] if x["id"] == lb_id), None)
    assert lb and lb["status"] == "build"
    api("DELETE", f"/api/sdn/load-balancers/{lb_id}")


def test_created_lb_appears_in_table(logged_in: Page, api):
    name = _LB_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_lbs(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/load-balancers" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    lb_id = resp.value.json().get("id")

    row = page.locator("#lbsBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    if lb_id:
        api("DELETE", f"/api/sdn/load-balancers/{lb_id}")


# ── delete from UI ────────────────────────────────────────────────────────────

def test_delete_lb_from_table(logged_in: Page, api):
    name = _LB_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/load-balancers", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create load balancer via API")
    lb_id = r["body"]["id"]

    page = logged_in
    _go_lbs(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#lbsBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#lbsBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/load-balancers")
    assert lb_id not in [x["id"] for x in r2["body"]]


# ── full roundtrip ────────────────────────────────────────────────────────────

def test_create_and_delete_full_roundtrip(logged_in: Page):
    name = _LB_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_lbs(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/load-balancers" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)

    row = page.locator("#lbsBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#lbsBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_api_list_returns_list(api):
    r = api("GET", "/api/sdn/load-balancers")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_create_minimal(api):
    name = _LB_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/load-balancers", {"name": name})
    assert r["status"] in (200, 201)
    assert r["body"].get("id")
    api("DELETE", f"/api/sdn/load-balancers/{r['body']['id']}")


def test_api_create_missing_name_returns_422(api):
    r = api("POST", "/api/sdn/load-balancers", {"project_id": "proj-abc"})
    assert r["status"] == 422


def test_api_delete_lb(api):
    r = api("POST", "/api/sdn/load-balancers", {"name": _LB_NAME + uuid.uuid4().hex[:8]})
    lb_id = r["body"]["id"]
    r2 = api("DELETE", f"/api/sdn/load-balancers/{lb_id}")
    assert r2["status"] in (200, 204)
    r3 = api("GET", "/api/sdn/load-balancers")
    assert lb_id not in [x["id"] for x in r3["body"]]


def test_api_delete_not_found(api):
    r = api("DELETE", "/api/sdn/load-balancers/nonexistent-e2e-lb")
    assert r["status"] == 404


def test_api_filter_by_project_id(api):
    pid = "proj-lb-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/load-balancers", {
        "name": _LB_NAME + uuid.uuid4().hex[:8],
        "project_id": pid,
    })
    lb_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/load-balancers?project_id={pid}")
    assert r2["status"] == 200
    ids = [x["id"] for x in r2["body"]]
    assert lb_id in ids
    for x in r2["body"]:
        assert x["project_id"] == pid
    api("DELETE", f"/api/sdn/load-balancers/{lb_id}")


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_sidebar_link_activates_lbs_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='lbs']")
    if link.count() == 0:
        pytest.skip("Sidebar lbs link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "lbs" in page.url


def test_sidebar_link_shows_lbs_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='lbs']")
    if link.count() == 0:
        pytest.skip("Sidebar lbs link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#panel-lbs")).to_be_visible(timeout=5_000)


def test_sidebar_lbs_link_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='lbs']")
    if link.count() == 0:
        pytest.skip("Sidebar lbs link not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "active" in (link.first.get_attribute("class") or "")


# ── no JS errors ──────────────────────────────────────────────────────────────

def test_lbs_no_js_errors(logged_in: Page):
    page = logged_in
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    _go_lbs(page)
    page.wait_for_load_state("networkidle")
    assert [e for e in errors if "Uncaught" in e or "TypeError" in e] == []


# ── Webhook → UI integration ──────────────────────────────────────────────────

def test_webhook_lb_created_appears_in_table(logged_in: Page, api):
    page = logged_in
    _go_lbs(page)
    page.wait_for_load_state("networkidle")

    info = _seed_lb(api)
    page.reload()
    page.wait_for_load_state("networkidle")

    expect(
        page.locator("#lbsBody").get_by_text(info["name"]).first
    ).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/load-balancers/{info['id']}")


def test_webhook_lb_deleted_removes_row(logged_in: Page, api):
    info = _seed_lb(api)
    page = logged_in
    _go_lbs(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#lbsBody").get_by_text(info["name"])
    expect(row.first).to_be_visible(timeout=8_000)

    api("POST", "/webhooks/nervum", {
        "event_type": "load_balancer.deleted",
        "resource_type": "load_balancer",
        "resource_id": info["id"],
        "payload": {},
    })
    page.reload()
    page.wait_for_load_state("networkidle")
    expect(row.first).to_be_hidden(timeout=8_000)


def test_webhook_lb_status_changed(api):
    """load_balancer.status_changed updates status in replica."""
    info = _seed_lb(api, status="build")
    api("POST", "/webhooks/nervum", {
        "event_type": "load_balancer.status_changed",
        "resource_type": "load_balancer",
        "resource_id": info["id"],
        "payload": {"id": info["id"], "name": info["name"], "status": "active"},
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/load-balancers")
        lb = next((x for x in r["body"] if x["id"] == info["id"]), None)
        if lb and lb["status"] == "active":
            break
        time.sleep(0.2)
    r = api("GET", "/api/sdn/load-balancers")
    lb = next((x for x in r["body"] if x["id"] == info["id"]), None)
    assert lb and lb["status"] == "active"
    api("DELETE", f"/api/sdn/load-balancers/{info['id']}")
