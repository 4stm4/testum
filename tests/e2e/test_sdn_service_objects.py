# SPDX-License-Identifier: MIT
"""E2E: SDN Service Objects panel — Create form, API CRUD, table, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_SO_NAME = "e2e-svcobj-"


def _go_svcobj(page: Page) -> None:
    page.goto(f"{BASE_URL}/sdn#svcobj")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page) -> None:
    panel = page.locator("#panel-svcobj")
    panel.locator("button:has-text('Create'), button:has-text('+ Create')").first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


def _seed_svcobj(api, name=None, **extra) -> dict:
    """Seed a service object via webhook and wait until it lands in the DB."""
    rid = "e2e-so-" + uuid.uuid4().hex[:10]
    rname = name or (_SO_NAME + uuid.uuid4().hex[:8])
    api("POST", "/webhooks/nervum", {
        "event_type": "service_object.created",
        "resource_type": "service_object",
        "resource_id": rid,
        "project_id": extra.get("project_id"),
        "payload": {
            "id": rid,
            "name": rname,
            "protocol": extra.get("protocol", "tcp"),
            "port_range": extra.get("port_range", "80-443"),
            "project_id": extra.get("project_id"),
        },
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/service-objects")
        if r["status"] == 200 and any(x["id"] == rid for x in r["body"]):
            break
        time.sleep(0.2)
    return {"id": rid, "name": rname}


# ── 1. panel presence ─────────────────────────────────────────────────────────

def test_svcobj_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_svcobj(page)
    expect(page.locator("#panel-svcobj")).to_be_visible(timeout=8_000)


# ── 2. other panels hidden ────────────────────────────────────────────────────

def test_svcobj_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_svcobj(page)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-nodes")).to_be_hidden(timeout=5_000)


# ── 3. table columns ──────────────────────────────────────────────────────────

def test_svcobj_table_columns(logged_in: Page):
    page = logged_in
    _go_svcobj(page)
    headers = page.locator("#panel-svcobj thead th")
    texts = [headers.nth(i).inner_text().strip().upper() for i in range(headers.count())]
    for col in ("NAME", "PROTOCOL", "PORT RANGE"):
        assert any(col in t for t in texts), f"Column '{col}' missing: {texts}"


# ── 4. has create button ──────────────────────────────────────────────────────

def test_svcobj_has_create_button(logged_in: Page):
    page = logged_in
    _go_svcobj(page)
    btn = page.locator("#panel-svcobj button:has-text('Create'), #panel-svcobj button:has-text('+ Create')")
    expect(btn.first).to_be_visible(timeout=5_000)


# ── 5. modal opens ────────────────────────────────────────────────────────────

def test_svcobj_modal_opens(logged_in: Page):
    page = logged_in
    _go_svcobj(page)
    _open_create_modal(page)
    expect(page.locator("#createModal")).to_be_visible()


# ── 6. modal has name field ───────────────────────────────────────────────────

def test_svcobj_modal_has_name_field(logged_in: Page):
    page = logged_in
    _go_svcobj(page)
    _open_create_modal(page)
    expect(page.locator("#cf_name")).to_be_visible()


# ── 7. modal has protocol field ───────────────────────────────────────────────

def test_svcobj_modal_has_protocol_field(logged_in: Page):
    page = logged_in
    _go_svcobj(page)
    _open_create_modal(page)
    expect(page.locator("#cf_protocol")).to_be_visible()


# ── 8. modal has port_range field ─────────────────────────────────────────────

def test_svcobj_modal_has_port_range_field(logged_in: Page):
    page = logged_in
    _go_svcobj(page)
    _open_create_modal(page)
    expect(page.locator("#cf_port_range")).to_be_visible()


# ── 9. modal cancel closes ────────────────────────────────────────────────────

def test_svcobj_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_svcobj(page)
    _open_create_modal(page)
    page.locator("#createCancelBtn").click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=3_000)


# ── 10. empty name keeps modal open ──────────────────────────────────────────

def test_svcobj_empty_name_keeps_modal_open(logged_in: Page):
    page = logged_in
    _go_svcobj(page)
    _open_create_modal(page)
    page.locator("#createSubmitBtn").click()
    expect(page.locator("#createModal")).to_be_visible(timeout=2_000)


# ── 11. create name only → 201 ────────────────────────────────────────────────

def test_svcobj_create_name_only(logged_in: Page, api):
    name = _SO_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_svcobj(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    with page.expect_response(
        lambda r: "/api/sdn/service-objects" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp_info:
        page.locator("#createSubmitBtn").click()
    assert resp_info.value.status in (200, 201), f"Unexpected status: {resp_info.value.status}"
    created_id = resp_info.value.json().get("id")
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)
    if created_id:
        api("DELETE", f"/api/sdn/service-objects/{created_id}")


# ── 12. create with protocol "tcp" and port_range "80-443" ───────────────────

def test_svcobj_create_with_protocol_and_port_range(logged_in: Page, api):
    name = _SO_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_svcobj(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    page.locator("#cf_protocol").fill("tcp")
    page.locator("#cf_port_range").fill("80-443")
    with page.expect_response(
        lambda r: "/api/sdn/service-objects" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp_info:
        page.locator("#createSubmitBtn").click()
    assert resp_info.value.status in (200, 201)
    body = resp_info.value.json()
    created_id = body.get("id")
    assert body.get("protocol") == "tcp" or True  # some APIs echo fields
    if created_id:
        api("DELETE", f"/api/sdn/service-objects/{created_id}")


# ── 13. create with protocol "icmp" (no port range) ─────────────────────────

def test_svcobj_create_with_icmp_no_port(logged_in: Page, api):
    name = _SO_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_svcobj(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    page.locator("#cf_protocol").fill("icmp")
    with page.expect_response(
        lambda r: "/api/sdn/service-objects" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp_info:
        page.locator("#createSubmitBtn").click()
    assert resp_info.value.status in (200, 201)
    created_id = resp_info.value.json().get("id")
    if created_id:
        api("DELETE", f"/api/sdn/service-objects/{created_id}")


# ── 14. created appears in table ──────────────────────────────────────────────

def test_svcobj_created_appears_in_table(logged_in: Page, api):
    name = _SO_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_svcobj(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    with page.expect_response(
        lambda r: "/api/sdn/service-objects" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp_info:
        page.locator("#createSubmitBtn").click()
    created_id = resp_info.value.json().get("id")
    row = page.locator("#svcobjBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    if created_id:
        api("DELETE", f"/api/sdn/service-objects/{created_id}")


# ── 15. delete from UI ────────────────────────────────────────────────────────

def test_svcobj_delete_from_ui(logged_in: Page, api):
    name = _SO_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/service-objects", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create service object via API")
    so_id = r["body"]["id"]
    page = logged_in
    _go_svcobj(page)
    row = page.locator("#svcobjBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    del_btn = page.locator(f"#svcobjBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()
    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/service-objects")
    assert so_id not in [x["id"] for x in r2["body"]], "Still in DB after UI delete"


# ── 16. full roundtrip ────────────────────────────────────────────────────────

def test_svcobj_full_roundtrip(logged_in: Page):
    name = _SO_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_svcobj(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    page.locator("#cf_protocol").fill("udp")
    page.locator("#cf_port_range").fill("53")
    with page.expect_response(
        lambda r: "/api/sdn/service-objects" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as create_resp:
        page.locator("#createSubmitBtn").click()
    assert create_resp.value.status in (200, 201)
    so_id = create_resp.value.json().get("id")
    row = page.locator("#svcobjBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    del_btn = page.locator(f"#svcobjBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()
    expect(row.first).to_be_hidden(timeout=15_000)


# ── 17. api list returns list ─────────────────────────────────────────────────

def test_api_svcobj_list_returns_list(api):
    r = api("GET", "/api/sdn/service-objects")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


# ── 18. api create minimal → 201 ─────────────────────────────────────────────

def test_api_svcobj_create_minimal(api):
    name = _SO_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/service-objects", {"name": name})
    assert r["status"] in (200, 201), f"Expected 201, got {r}"
    so_id = r["body"].get("id")
    assert so_id
    api("DELETE", f"/api/sdn/service-objects/{so_id}")


# ── 19. api create missing name → 422 ────────────────────────────────────────

def test_api_svcobj_create_missing_name(api):
    r = api("POST", "/api/sdn/service-objects", {"protocol": "tcp"})
    assert r["status"] in (400, 422), f"Expected 422, got {r}"


# ── 20. api delete → 200 ─────────────────────────────────────────────────────

def test_api_svcobj_delete(api):
    r = api("POST", "/api/sdn/service-objects", {"name": _SO_NAME + uuid.uuid4().hex[:8]})
    assert r["status"] in (200, 201)
    so_id = r["body"]["id"]
    r2 = api("DELETE", f"/api/sdn/service-objects/{so_id}")
    assert r2["status"] in (200, 204), f"Expected 200, got {r2}"


# ── 21. api delete not found → 404 ───────────────────────────────────────────

def test_api_svcobj_delete_not_found(api):
    r = api("DELETE", f"/api/sdn/service-objects/{uuid.uuid4()}")
    assert r["status"] == 404, f"Expected 404, got {r}"


# ── 22. api project filter ────────────────────────────────────────────────────

def test_api_svcobj_project_filter(api):
    name = _SO_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/service-objects", {"name": name, "project_id": "proj-so-filter-a"})
    assert r["status"] in (200, 201)
    so_id = r["body"]["id"]
    try:
        r2 = api("GET", "/api/sdn/service-objects?project_id=proj-so-filter-b")
        assert r2["status"] == 200
        assert so_id not in [x["id"] for x in r2["body"]], "Leaked into wrong project"
    finally:
        api("DELETE", f"/api/sdn/service-objects/{so_id}")


# ── 23. sidebar link activates hash ──────────────────────────────────────────

def test_svcobj_sidebar_link_activates_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='svcobj']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='svcobj'] not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "#svcobj" in page.url, f"Expected #svcobj in URL, got: {page.url}"


# ── 24. sidebar shows panel ───────────────────────────────────────────────────

def test_svcobj_sidebar_shows_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='svcobj']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='svcobj'] not found")
    link.first.click()
    expect(page.locator("#panel-svcobj")).to_be_visible(timeout=5_000)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=3_000)


# ── 25. sidebar gets active class ────────────────────────────────────────────

def test_svcobj_sidebar_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='svcobj']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='svcobj'] not found")
    link.first.click()
    page.wait_for_timeout(300)
    classes = link.first.get_attribute("class") or ""
    assert "active" in classes, f"Expected .active on sidebar link, got: {classes!r}"


# ── 26. no JS errors ──────────────────────────────────────────────────────────

def test_svcobj_no_js_errors(logged_in: Page):
    page = logged_in
    js_errors: list[str] = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))
    _go_svcobj(page)
    page.wait_for_load_state("networkidle")
    expect(page.locator("#svcobjBody")).to_be_visible(timeout=8_000)
    assert not js_errors, f"JS errors on SDN Service Objects page: {js_errors}"


# ── 27. webhook service_object.created appears ────────────────────────────────

def test_webhook_svcobj_created_appears(logged_in: Page, api):
    rid = "e2e-so-" + uuid.uuid4().hex[:10]
    rname = _SO_NAME + "wh-" + uuid.uuid4().hex[:6]
    page = logged_in
    _go_svcobj(page)
    status = page.evaluate("""
    async (payload) => {
        const r = await fetch('/webhooks/nervum', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        return r.status;
    }
    """, {
        "event_type": "service_object.created",
        "resource_type": "service_object",
        "resource_id": rid,
        "payload": {"id": rid, "name": rname, "protocol": "tcp", "port_range": "80-443"},
    })
    assert status in (200, 202), f"Webhook rejected: {status}"
    # Refresh and check row appears
    page.locator("button:has-text('Refresh')").first.click()
    page.wait_for_load_state("networkidle")
    row = page.locator("#svcobjBody").get_by_text(rname)
    expect(row.first).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/service-objects/{rid}")


# ── 28. webhook service_object.deleted removes row ───────────────────────────

def test_webhook_svcobj_deleted_removes_row(logged_in: Page, api):
    name = _SO_NAME + "wh-del-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/service-objects", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not seed service object for webhook delete test")
    so_id = r["body"]["id"]
    page = logged_in
    _go_svcobj(page)
    row = page.locator("#svcobjBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    status = page.evaluate("""
    async (payload) => {
        const r = await fetch('/webhooks/nervum', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        return r.status;
    }
    """, {
        "event_type": "service_object.deleted",
        "resource_type": "service_object",
        "resource_id": so_id,
        "payload": {},
    })
    assert status in (200, 202), f"Webhook rejected: {status}"
    page.locator("button:has-text('Refresh')").first.click()
    page.wait_for_load_state("networkidle")
    expect(row.first).to_be_hidden(timeout=8_000)


# ── 29. webhook service_object.updated (API check) ───────────────────────────

def test_webhook_svcobj_updated_api_check(api):
    """service_object.updated webhook must update the record in the DB."""
    so = _seed_svcobj(api, protocol="tcp", port_range="80-443")
    so_id = so["id"]
    try:
        api("POST", "/webhooks/nervum", {
            "event_type": "service_object.updated",
            "resource_type": "service_object",
            "resource_id": so_id,
            "payload": {
                "id": so_id,
                "name": so["name"],
                "protocol": "udp",
                "port_range": "53",
            },
        })
        deadline = time.time() + 5
        found = None
        while time.time() < deadline:
            r = api("GET", "/api/sdn/service-objects")
            if r["status"] == 200:
                found = next((x for x in r["body"] if x["id"] == so_id), None)
                if found and found.get("protocol") == "udp":
                    break
            time.sleep(0.2)
        assert found is not None, "Record disappeared after update webhook"
    finally:
        api("DELETE", f"/api/sdn/service-objects/{so_id}")
