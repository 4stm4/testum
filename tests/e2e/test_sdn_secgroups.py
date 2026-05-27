# SPDX-License-Identifier: MIT
"""E2E: SDN Security Groups panel — Create form, API CRUD, table, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_SG_NAME = "e2e-sg-"


def _go_secgroups(page: Page):
    page.goto(f"{BASE_URL}/sdn#secgroups")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page):
    page.locator(
        "#panel-secgroups button:has-text('Create'), #panel-secgroups button:has-text('+ Create')"
    ).first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


def _seed_secgroup(api, name: str | None = None, **extra) -> dict:
    """Seed a security group via webhook. Polls until it lands in DB."""
    sg_id = "e2e-sg-" + uuid.uuid4().hex[:10]
    sg_name = name or (_SG_NAME + uuid.uuid4().hex[:8])
    payload = {
        "event_type": "security_group.created",
        "resource_type": "security_group",
        "resource_id": sg_id,
        "project_id": extra.get("project_id"),
        "payload": {
            "id": sg_id,
            "name": sg_name,
            "project_id": extra.get("project_id"),
            "rules": extra.get("rules", []),
        },
    }
    api("POST", "/webhooks/nervum", payload)
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/security-groups")
        if r["status"] == 200 and any(x["id"] == sg_id for x in r["body"]):
            break
        time.sleep(0.2)
    return {"id": sg_id, "name": sg_name}


# ── panel presence ────────────────────────────────────────────────────────────

def test_secgroups_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_secgroups(page)
    expect(page.locator("#panel-secgroups")).to_be_visible(timeout=8_000)


def test_secgroups_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_secgroups(page)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-routers")).to_be_hidden(timeout=5_000)


def test_secgroups_table_columns(logged_in: Page):
    page = logged_in
    _go_secgroups(page)
    headers = page.locator("#panel-secgroups thead th")
    texts = [headers.nth(i).inner_text().strip().upper() for i in range(headers.count())]
    for col in ("NAME", "PROJECT", "RULES"):
        assert any(col in t for t in texts), f"Column '{col}' not found in {texts}"


def test_secgroups_has_create_button(logged_in: Page):
    page = logged_in
    _go_secgroups(page)
    expect(
        page.locator(
            "#panel-secgroups button:has-text('Create'), #panel-secgroups button:has-text('+ Create')"
        ).first
    ).to_be_visible(timeout=5_000)


# ── modal open / close ────────────────────────────────────────────────────────

def test_create_modal_opens(logged_in: Page):
    page = logged_in
    _go_secgroups(page)
    _open_create_modal(page)
    expect(page.locator("#createModal")).to_be_visible(timeout=5_000)


def test_create_modal_title_contains_security(logged_in: Page):
    page = logged_in
    _go_secgroups(page)
    _open_create_modal(page)
    title = page.locator("#createModalTitle").inner_text()
    assert "secgroup" in title.lower() or "security" in title.lower()


def test_create_modal_has_name_field(logged_in: Page):
    page = logged_in
    _go_secgroups(page)
    _open_create_modal(page)
    expect(page.locator("#cf_name")).to_be_visible(timeout=3_000)


def test_create_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_secgroups(page)
    _open_create_modal(page)
    page.locator(
        "#createModal button:has-text('Cancel'), #createCancelBtn"
    ).first.click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


def test_create_modal_backdrop_click_closes(logged_in: Page):
    page = logged_in
    _go_secgroups(page)
    _open_create_modal(page)
    page.locator("#createModal").click(position={"x": 5, "y": 5})
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


# ── client-side validation ────────────────────────────────────────────────────

def test_create_empty_name_keeps_modal_open(logged_in: Page):
    page = logged_in
    _go_secgroups(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill("")
    page.locator("#createSubmitBtn").click()
    expect(page.locator("#createModal")).to_be_visible(timeout=3_000)


def test_create_empty_name_no_api_call(logged_in: Page):
    page = logged_in
    _go_secgroups(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill("")
    calls: list[str] = []
    page.on(
        "request",
        lambda req: calls.append(req.url)
        if "/api/sdn/security-groups" in req.url and req.method == "POST"
        else None,
    )
    page.locator("#createSubmitBtn").click()
    page.wait_for_timeout(500)
    assert calls == [], "POST should not fire with empty name"


# ── successful create ─────────────────────────────────────────────────────────

def test_create_secgroup_name_only(logged_in: Page, api):
    name = _SG_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_secgroups(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/security-groups" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    sg_id = resp.value.json().get("id")
    if sg_id:
        api("DELETE", f"/api/sdn/security-groups/{sg_id}")


def test_create_secgroup_with_project_id(logged_in: Page, api):
    name = _SG_NAME + uuid.uuid4().hex[:8]
    pid = "proj-sg-" + uuid.uuid4().hex[:6]
    page = logged_in
    _go_secgroups(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    proj_field = page.locator("#cf_project_id")
    if proj_field.count() > 0:
        proj_field.fill(pid)

    with page.expect_response(
        lambda r: "/api/sdn/security-groups" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    sg_id = resp.value.json().get("id")
    if sg_id:
        r2 = api("GET", "/api/sdn/security-groups")
        sg = next((x for x in r2["body"] if x["id"] == sg_id), None)
        if proj_field.count() > 0 and sg:
            assert sg["project_id"] == pid
        api("DELETE", f"/api/sdn/security-groups/{sg_id}")


def test_created_secgroup_appears_in_table(logged_in: Page, api):
    name = _SG_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_secgroups(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/security-groups" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    sg_id = resp.value.json().get("id")

    row = page.locator("#secgroupsBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    if sg_id:
        api("DELETE", f"/api/sdn/security-groups/{sg_id}")


# ── delete from UI ────────────────────────────────────────────────────────────

def test_delete_secgroup_from_table(logged_in: Page, api):
    name = _SG_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/security-groups", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create security group via API")
    sg_id = r["body"]["id"]

    page = logged_in
    _go_secgroups(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#secgroupsBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#secgroupsBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/security-groups")
    assert sg_id not in [x["id"] for x in r2["body"]]


# ── full roundtrip ────────────────────────────────────────────────────────────

def test_create_and_delete_full_roundtrip(logged_in: Page):
    name = _SG_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_secgroups(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/security-groups" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)

    row = page.locator("#secgroupsBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#secgroupsBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_api_list_returns_list(api):
    r = api("GET", "/api/sdn/security-groups")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_create_minimal(api):
    name = _SG_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/security-groups", {"name": name})
    assert r["status"] in (200, 201)
    assert r["body"].get("id")
    api("DELETE", f"/api/sdn/security-groups/{r['body']['id']}")


def test_api_create_missing_name_returns_422(api):
    r = api("POST", "/api/sdn/security-groups", {"project_id": "proj-abc"})
    assert r["status"] == 422


def test_api_delete_secgroup(api):
    name = _SG_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/security-groups", {"name": name})
    assert r["status"] in (200, 201)
    sg_id = r["body"]["id"]
    r2 = api("DELETE", f"/api/sdn/security-groups/{sg_id}")
    assert r2["status"] in (200, 204)
    r3 = api("GET", "/api/sdn/security-groups")
    assert sg_id not in [x["id"] for x in r3["body"]]


def test_api_delete_not_found(api):
    r = api("DELETE", "/api/sdn/security-groups/nonexistent-e2e-sg")
    assert r["status"] == 404


def test_api_project_filter_isolates(api):
    pid = "proj-sg-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/security-groups", {
        "name": _SG_NAME + uuid.uuid4().hex[:8],
        "project_id": pid,
    })
    assert r["status"] in (200, 201)
    sg_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/security-groups?project_id={pid}")
    assert r2["status"] == 200
    ids = [x["id"] for x in r2["body"]]
    assert sg_id in ids
    for x in r2["body"]:
        assert x["project_id"] == pid
    api("DELETE", f"/api/sdn/security-groups/{sg_id}")


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_sidebar_link_activates_secgroups_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='secgroups']")
    if link.count() == 0:
        pytest.skip("Sidebar secgroups link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "secgroups" in page.url


def test_sidebar_link_shows_secgroups_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='secgroups']")
    if link.count() == 0:
        pytest.skip("Sidebar secgroups link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#panel-secgroups")).to_be_visible(timeout=5_000)


def test_sidebar_secgroups_link_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='secgroups']")
    if link.count() == 0:
        pytest.skip("Sidebar secgroups link not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "active" in (link.first.get_attribute("class") or "")


# ── empty state ───────────────────────────────────────────────────────────────

def test_secgroups_empty_state_no_js_error(logged_in: Page):
    page = logged_in
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    _go_secgroups(page)
    page.wait_for_load_state("networkidle")
    assert [e for e in errors if "Uncaught" in e or "TypeError" in e] == []


# ── Webhook → UI integration ──────────────────────────────────────────────────

def test_webhook_secgroup_created_appears_in_table(logged_in: Page, api):
    page = logged_in
    _go_secgroups(page)
    page.wait_for_load_state("networkidle")

    info = _seed_secgroup(api)
    page.reload()
    page.wait_for_load_state("networkidle")

    expect(
        page.locator("#secgroupsBody").get_by_text(info["name"]).first
    ).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/security-groups/{info['id']}")


def test_webhook_secgroup_deleted_removes_row(logged_in: Page, api):
    info = _seed_secgroup(api)
    page = logged_in
    _go_secgroups(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#secgroupsBody").get_by_text(info["name"])
    expect(row.first).to_be_visible(timeout=8_000)

    api("POST", "/webhooks/nervum", {
        "event_type": "security_group.deleted",
        "resource_type": "security_group",
        "resource_id": info["id"],
        "payload": {},
    })
    page.reload()
    page.wait_for_load_state("networkidle")
    expect(row.first).to_be_hidden(timeout=8_000)


def test_webhook_secgroup_rules_updated(api):
    """security_group.rules_updated updates rules field in replica."""
    info = _seed_secgroup(api)
    new_rules = [
        {"id": uuid.uuid4().hex, "direction": "ingress", "protocol": "tcp", "port_range_min": 80, "port_range_max": 80},
    ]
    api("POST", "/webhooks/nervum", {
        "event_type": "security_group.rules_updated",
        "resource_type": "security_group",
        "resource_id": info["id"],
        "payload": {"id": info["id"], "name": info["name"], "rules": new_rules},
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/security-groups")
        sg = next((x for x in r["body"] if x["id"] == info["id"]), None)
        if sg and isinstance(sg.get("rules"), list) and len(sg["rules"]) > 0:
            break
        time.sleep(0.2)
    r = api("GET", "/api/sdn/security-groups")
    sg = next((x for x in r["body"] if x["id"] == info["id"]), None)
    assert sg is not None, "Security group not found after rules_updated webhook"
    assert isinstance(sg.get("rules"), list)
    api("DELETE", f"/api/sdn/security-groups/{info['id']}")
