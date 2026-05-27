# SPDX-License-Identifier: MIT
"""E2E: SDN Apply Schedules panel — Create form, API CRUD, table, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_AS_NAME = "e2e-sched-"


def _go_sched(page: Page):
    page.goto(f"{BASE_URL}/sdn#sched")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page):
    page.locator(
        "#panel-sched button:has-text('Create'), #panel-sched button:has-text('+ Create')"
    ).first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


def _seed_apply_schedule(api, name=None, **extra):
    rid = "e2e-sched-" + uuid.uuid4().hex[:10]
    rname = name or ("e2e-sched-" + uuid.uuid4().hex[:8])
    api("POST", "/webhooks/nervum", {
        "event_type": "apply_schedule.created",
        "resource_type": "apply_schedule",
        "resource_id": rid,
        "project_id": extra.get("project_id"),
        "payload": {"id": rid, "name": rname, "status": extra.get("status", "active")},
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/apply-schedules")
        if r["status"] == 200 and any(x["id"] == rid for x in r["body"]):
            break
        time.sleep(0.2)
    return {"id": rid, "name": rname}


# ── panel presence ────────────────────────────────────────────────────────────

def test_sched_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_sched(page)
    expect(page.locator("#panel-sched")).to_be_visible(timeout=8_000)


def test_sched_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_sched(page)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-routers")).to_be_hidden(timeout=5_000)


def test_sched_table_columns(logged_in: Page):
    page = logged_in
    _go_sched(page)
    headers = page.locator("#panel-sched thead th")
    texts = [headers.nth(i).inner_text().strip().upper() for i in range(headers.count())]
    assert any("NAME" in t for t in texts), f"NAME column missing: {texts}"
    assert any("STATUS" in t for t in texts), f"STATUS column missing: {texts}"
    assert any("UPDATED" in t for t in texts), f"UPDATED column missing: {texts}"


def test_sched_has_create_button(logged_in: Page):
    page = logged_in
    _go_sched(page)
    expect(page.locator(
        "#panel-sched button:has-text('Create'), #panel-sched button:has-text('+ Create')"
    ).first).to_be_visible(timeout=5_000)


# ── modal open / close ────────────────────────────────────────────────────────

def test_create_modal_opens(logged_in: Page):
    page = logged_in
    _go_sched(page)
    _open_create_modal(page)
    expect(page.locator("#createModal")).to_be_visible(timeout=5_000)


def test_create_modal_title(logged_in: Page):
    page = logged_in
    _go_sched(page)
    _open_create_modal(page)
    title = page.locator("#createModalTitle").inner_text()
    assert title.strip() != "", f"Modal title is empty"


def test_create_modal_has_name_field(logged_in: Page):
    page = logged_in
    _go_sched(page)
    _open_create_modal(page)
    expect(page.locator("#cf_name")).to_be_visible(timeout=3_000)


def test_create_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_sched(page)
    _open_create_modal(page)
    page.locator("#createModal button:has-text('Cancel'), #createCancelBtn").first.click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


def test_create_modal_backdrop_click_closes(logged_in: Page):
    page = logged_in
    _go_sched(page)
    _open_create_modal(page)
    page.locator("#createModal").click(position={"x": 5, "y": 5})
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


# ── client-side validation ────────────────────────────────────────────────────

def test_create_empty_name_keeps_modal_open(logged_in: Page):
    page = logged_in
    _go_sched(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill("")
    page.locator("#createSubmitBtn").click()
    expect(page.locator("#createModal")).to_be_visible(timeout=3_000)


# ── successful create ─────────────────────────────────────────────────────────

def test_create_sched_name_only(logged_in: Page, api):
    name = _AS_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_sched(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/apply-schedules" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201), f"Create failed: {resp.value.status}"
    as_id = resp.value.json().get("id")
    if as_id:
        api("DELETE", f"/api/sdn/apply-schedules/{as_id}")


def test_create_sched_initial_status_is_active(api):
    """Newly created apply schedule has status 'active'."""
    name = _AS_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/apply-schedules", {"name": name})
    assert r["status"] in (200, 201)
    as_id = r["body"]["id"]
    r2 = api("GET", "/api/sdn/apply-schedules")
    rec = next((x for x in r2["body"] if x["id"] == as_id), None)
    assert rec is not None
    assert rec["status"] == "active", f"Expected 'active', got: {rec['status']}"
    api("DELETE", f"/api/sdn/apply-schedules/{as_id}")


def test_create_sched_with_project_id(logged_in: Page, api):
    name = _AS_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_sched(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    pid_field = page.locator("#cf_project_id")
    if pid_field.count() > 0:
        pid_field.fill("proj-e2e-sched")

    with page.expect_response(
        lambda r: "/api/sdn/apply-schedules" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    as_id = resp.value.json().get("id")
    if as_id:
        api("DELETE", f"/api/sdn/apply-schedules/{as_id}")


# ── table update after create ─────────────────────────────────────────────────

def test_created_sched_appears_in_table(logged_in: Page, api):
    name = _AS_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_sched(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/apply-schedules" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    as_id = resp.value.json().get("id")

    row = page.locator("#schedBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    if as_id:
        api("DELETE", f"/api/sdn/apply-schedules/{as_id}")


# ── delete from UI ────────────────────────────────────────────────────────────

def test_delete_sched_from_table(logged_in: Page, api):
    name = _AS_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/apply-schedules", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create apply schedule via API")
    as_id = r["body"]["id"]

    page = logged_in
    _go_sched(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#schedBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#schedBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/apply-schedules")
    assert as_id not in [x["id"] for x in r2["body"]]


# ── full roundtrip ────────────────────────────────────────────────────────────

def test_create_and_delete_full_roundtrip(logged_in: Page):
    name = _AS_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_sched(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/apply-schedules" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)

    row = page.locator("#schedBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#schedBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_api_list_returns_list(api):
    r = api("GET", "/api/sdn/apply-schedules")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_create_minimal(api):
    name = _AS_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/apply-schedules", {"name": name})
    assert r["status"] in (200, 201), f"Expected 201, got {r}"
    assert r["body"].get("id")
    api("DELETE", f"/api/sdn/apply-schedules/{r['body']['id']}")


def test_api_create_missing_name_returns_422(api):
    r = api("POST", "/api/sdn/apply-schedules", {"project_id": "proj-abc"})
    assert r["status"] == 422, f"Expected 422, got {r}"


def test_api_delete_sched(api):
    r = api("POST", "/api/sdn/apply-schedules", {"name": _AS_NAME + uuid.uuid4().hex[:8]})
    assert r["status"] in (200, 201)
    as_id = r["body"]["id"]
    r2 = api("DELETE", f"/api/sdn/apply-schedules/{as_id}")
    assert r2["status"] in (200, 204)
    r3 = api("GET", "/api/sdn/apply-schedules")
    assert as_id not in [x["id"] for x in r3["body"]]


def test_api_delete_not_found(api):
    r = api("DELETE", "/api/sdn/apply-schedules/nonexistent-e2e-sched")
    assert r["status"] == 404, f"Expected 404, got {r}"


def test_api_filter_by_project_id(api):
    pid = "proj-sched-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/apply-schedules", {"name": _AS_NAME + uuid.uuid4().hex[:8], "project_id": pid})
    assert r["status"] in (200, 201)
    as_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/apply-schedules?project_id={pid}")
    assert r2["status"] == 200
    ids = [x["id"] for x in r2["body"]]
    assert as_id in ids
    for x in r2["body"]:
        assert x["project_id"] == pid
    api("DELETE", f"/api/sdn/apply-schedules/{as_id}")


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_sidebar_link_activates_sched_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='sched']")
    if link.count() == 0:
        pytest.skip("Sidebar sched link not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "sched" in page.url, f"Expected 'sched' in URL, got: {page.url}"


def test_sidebar_link_shows_sched_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='sched']")
    if link.count() == 0:
        pytest.skip("Sidebar sched link not found")
    link.first.click()
    expect(page.locator("#panel-sched")).to_be_visible(timeout=5_000)


def test_sidebar_sched_link_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='sched']")
    if link.count() == 0:
        pytest.skip("Sidebar sched link not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "active" in (link.first.get_attribute("class") or "")


# ── no JS errors ──────────────────────────────────────────────────────────────

def test_no_js_errors_on_sched_panel(logged_in: Page):
    page = logged_in
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    _go_sched(page)
    page.wait_for_load_state("networkidle")
    assert [e for e in errors if "Uncaught" in e or "TypeError" in e] == []


# ── Webhook → integration ─────────────────────────────────────────────────────

def test_webhook_sched_created(logged_in: Page, api):
    page = logged_in
    _go_sched(page)
    page.wait_for_load_state("networkidle")

    info = _seed_apply_schedule(api)
    page.reload()
    page.wait_for_load_state("networkidle")

    expect(page.locator("#schedBody").get_by_text(info["name"]).first).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/apply-schedules/{info['id']}")


def test_webhook_sched_deleted(logged_in: Page, api):
    info = _seed_apply_schedule(api)
    page = logged_in
    _go_sched(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#schedBody").get_by_text(info["name"])
    expect(row.first).to_be_visible(timeout=8_000)

    api("POST", "/webhooks/nervum", {
        "event_type": "apply_schedule.deleted",
        "resource_type": "apply_schedule",
        "resource_id": info["id"],
        "payload": {},
    })
    page.reload()
    page.wait_for_load_state("networkidle")
    expect(row.first).to_be_hidden(timeout=8_000)


def test_webhook_sched_status_changed(api):
    """apply_schedule.status_changed: seed with status 'paused', send event with 'active', verify."""
    info = _seed_apply_schedule(api, status="paused")
    # Confirm seeded status
    r = api("GET", "/api/sdn/apply-schedules")
    rec = next((x for x in r["body"] if x["id"] == info["id"]), None)
    assert rec is not None, "Seeded record not found"
    assert rec.get("status") == "paused", f"Expected 'paused' after seed, got: {rec.get('status')}"

    api("POST", "/webhooks/nervum", {
        "event_type": "apply_schedule.status_changed",
        "resource_type": "apply_schedule",
        "resource_id": info["id"],
        "payload": {"id": info["id"], "name": info["name"], "status": "active"},
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/apply-schedules")
        rec = next((x for x in r["body"] if x["id"] == info["id"]), None)
        if rec and rec.get("status") == "active":
            break
        time.sleep(0.2)
    r = api("GET", "/api/sdn/apply-schedules")
    rec = next((x for x in r["body"] if x["id"] == info["id"]), None)
    assert rec is not None
    assert rec["status"] == "active", f"Status not updated to 'active': {rec}"
    api("DELETE", f"/api/sdn/apply-schedules/{info['id']}")
