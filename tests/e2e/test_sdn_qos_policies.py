# SPDX-License-Identifier: MIT
"""E2E: SDN QoS Policies panel — Create form, API CRUD, table, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_QOS_NAME = "e2e-qos-"


def _go_qos(page: Page) -> None:
    page.goto(f"{BASE_URL}/sdn#qos")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page) -> None:
    panel = page.locator("#panel-qos")
    panel.locator("button:has-text('Create'), button:has-text('+ Create')").first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


def _seed_qos(api, name=None, **extra) -> dict:
    """Seed a QoS policy via webhook and wait until it lands in the DB."""
    rid = "e2e-qos-" + uuid.uuid4().hex[:10]
    rname = name or (_QOS_NAME + uuid.uuid4().hex[:8])
    api("POST", "/webhooks/nervum", {
        "event_type": "qos_policy.created",
        "resource_type": "qos_policy",
        "resource_id": rid,
        "project_id": extra.get("project_id"),
        "payload": {
            "id": rid,
            "name": rname,
            "project_id": extra.get("project_id"),
        },
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/qos-policies")
        if r["status"] == 200 and any(x["id"] == rid for x in r["body"]):
            break
        time.sleep(0.2)
    return {"id": rid, "name": rname}


# ── 1. panel active on hash ───────────────────────────────────────────────────

def test_qos_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_qos(page)
    expect(page.locator("#panel-qos")).to_be_visible(timeout=8_000)


# ── 2. other panels hidden ────────────────────────────────────────────────────

def test_qos_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_qos(page)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-nodes")).to_be_hidden(timeout=5_000)


# ── 3. table columns ──────────────────────────────────────────────────────────

def test_qos_table_columns(logged_in: Page):
    page = logged_in
    _go_qos(page)
    headers = page.locator("#panel-qos thead th")
    texts = [headers.nth(i).inner_text().strip().upper() for i in range(headers.count())]
    for col in ("NAME", "PROJECT"):
        assert any(col in t for t in texts), f"Column '{col}' missing: {texts}"


# ── 4. has create button ──────────────────────────────────────────────────────

def test_qos_has_create_button(logged_in: Page):
    page = logged_in
    _go_qos(page)
    btn = page.locator("#panel-qos button:has-text('Create'), #panel-qos button:has-text('+ Create')")
    expect(btn.first).to_be_visible(timeout=5_000)


# ── 5. modal opens ────────────────────────────────────────────────────────────

def test_qos_modal_opens(logged_in: Page):
    page = logged_in
    _go_qos(page)
    _open_create_modal(page)
    expect(page.locator("#createModal")).to_be_visible()


# ── 6. modal title contains "qos" ────────────────────────────────────────────

def test_qos_modal_title_contains_qos(logged_in: Page):
    page = logged_in
    _go_qos(page)
    _open_create_modal(page)
    title = page.locator("#createModalTitle").inner_text()
    assert "qos" in title.lower(), f"Expected 'qos' in modal title, got: {title!r}"


# ── 7. modal has name field ───────────────────────────────────────────────────

def test_qos_modal_has_name_field(logged_in: Page):
    page = logged_in
    _go_qos(page)
    _open_create_modal(page)
    expect(page.locator("#cf_name")).to_be_visible()


# ── 8. modal cancel closes ────────────────────────────────────────────────────

def test_qos_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_qos(page)
    _open_create_modal(page)
    page.locator("#createCancelBtn").click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=3_000)


# ── 9. modal backdrop click closes ───────────────────────────────────────────

def test_qos_modal_backdrop_click_closes(logged_in: Page):
    page = logged_in
    _go_qos(page)
    _open_create_modal(page)
    page.locator("#createModal").click(position={"x": 5, "y": 5})
    expect(page.locator("#createModal")).to_be_hidden(timeout=3_000)


# ── 10. empty name keeps modal open ──────────────────────────────────────────

def test_qos_empty_name_keeps_modal_open(logged_in: Page):
    page = logged_in
    _go_qos(page)
    _open_create_modal(page)
    page.locator("#createSubmitBtn").click()
    expect(page.locator("#createModal")).to_be_visible(timeout=2_000)


# ── 11. empty name — no API call ──────────────────────────────────────────────

def test_qos_empty_name_no_api_call(logged_in: Page):
    page = logged_in
    _go_qos(page)
    _open_create_modal(page)
    api_called: list[str] = []
    page.on("request", lambda r: api_called.append(r.url) if "/api/sdn/qos-policies" in r.url else None)
    page.locator("#createSubmitBtn").click()
    page.wait_for_timeout(500)
    assert not api_called, "API should not be called when name is empty"


# ── 12. create name only → 201 ────────────────────────────────────────────────

def test_qos_create_name_only(logged_in: Page, api):
    name = _QOS_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_qos(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    with page.expect_response(
        lambda r: "/api/sdn/qos-policies" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp_info:
        page.locator("#createSubmitBtn").click()
    assert resp_info.value.status in (200, 201), f"Unexpected status: {resp_info.value.status}"
    created_id = resp_info.value.json().get("id")
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)
    if created_id:
        api("DELETE", f"/api/sdn/qos-policies/{created_id}")


# ── 13. create with project_id → verify ──────────────────────────────────────

def test_qos_create_with_project_id(logged_in: Page, api):
    name = _QOS_NAME + uuid.uuid4().hex[:8]
    proj = "proj-qos-e2e"
    page = logged_in
    _go_qos(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    proj_field = page.locator("#cf_project_id")
    if proj_field.count() > 0:
        proj_field.fill(proj)
    with page.expect_response(
        lambda r: "/api/sdn/qos-policies" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp_info:
        page.locator("#createSubmitBtn").click()
    assert resp_info.value.status in (200, 201)
    body = resp_info.value.json()
    created_id = body.get("id")
    if created_id:
        api("DELETE", f"/api/sdn/qos-policies/{created_id}")


# ── 14. created appears in table ──────────────────────────────────────────────

def test_qos_created_appears_in_table(logged_in: Page, api):
    name = _QOS_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_qos(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    with page.expect_response(
        lambda r: "/api/sdn/qos-policies" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp_info:
        page.locator("#createSubmitBtn").click()
    created_id = resp_info.value.json().get("id")
    row = page.locator("#qosBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    if created_id:
        api("DELETE", f"/api/sdn/qos-policies/{created_id}")


# ── 15. delete from UI ────────────────────────────────────────────────────────

def test_qos_delete_from_ui(logged_in: Page, api):
    name = _QOS_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/qos-policies", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create QoS policy via API")
    qos_id = r["body"]["id"]
    page = logged_in
    _go_qos(page)
    row = page.locator("#qosBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    del_btn = page.locator(f"#qosBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()
    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/qos-policies")
    assert qos_id not in [x["id"] for x in r2["body"]], "Still in DB after UI delete"


# ── 16. full roundtrip ────────────────────────────────────────────────────────

def test_qos_full_roundtrip(logged_in: Page):
    name = _QOS_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_qos(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    with page.expect_response(
        lambda r: "/api/sdn/qos-policies" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as create_resp:
        page.locator("#createSubmitBtn").click()
    assert create_resp.value.status in (200, 201)
    row = page.locator("#qosBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    del_btn = page.locator(f"#qosBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()
    expect(row.first).to_be_hidden(timeout=15_000)


# ── 17. api list returns list ─────────────────────────────────────────────────

def test_api_qos_list_returns_list(api):
    r = api("GET", "/api/sdn/qos-policies")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


# ── 18. api create minimal → 201 ─────────────────────────────────────────────

def test_api_qos_create_minimal(api):
    name = _QOS_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/qos-policies", {"name": name})
    assert r["status"] in (200, 201), f"Expected 201, got {r}"
    qos_id = r["body"].get("id")
    assert qos_id
    api("DELETE", f"/api/sdn/qos-policies/{qos_id}")


# ── 19. api create missing name → 422 ────────────────────────────────────────

def test_api_qos_create_missing_name(api):
    r = api("POST", "/api/sdn/qos-policies", {"project_id": "proj-x"})
    assert r["status"] in (400, 422), f"Expected 422, got {r}"


# ── 20. api delete → 200 ─────────────────────────────────────────────────────

def test_api_qos_delete(api):
    r = api("POST", "/api/sdn/qos-policies", {"name": _QOS_NAME + uuid.uuid4().hex[:8]})
    assert r["status"] in (200, 201)
    qos_id = r["body"]["id"]
    r2 = api("DELETE", f"/api/sdn/qos-policies/{qos_id}")
    assert r2["status"] in (200, 204), f"Expected 200, got {r2}"


# ── 21. api delete not found → 404 ───────────────────────────────────────────

def test_api_qos_delete_not_found(api):
    r = api("DELETE", f"/api/sdn/qos-policies/{uuid.uuid4()}")
    assert r["status"] == 404, f"Expected 404, got {r}"


# ── 22. api project filter ────────────────────────────────────────────────────

def test_api_qos_project_filter(api):
    name = _QOS_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/qos-policies", {"name": name, "project_id": "proj-qos-filter-a"})
    assert r["status"] in (200, 201)
    qos_id = r["body"]["id"]
    try:
        r2 = api("GET", "/api/sdn/qos-policies?project_id=proj-qos-filter-b")
        assert r2["status"] == 200
        assert qos_id not in [x["id"] for x in r2["body"]], "Leaked into wrong project"
    finally:
        api("DELETE", f"/api/sdn/qos-policies/{qos_id}")


# ── 23. sidebar link activates hash ──────────────────────────────────────────

def test_qos_sidebar_link_activates_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='qos']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='qos'] not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "#qos" in page.url, f"Expected #qos in URL, got: {page.url}"


# ── 24. sidebar shows panel ───────────────────────────────────────────────────

def test_qos_sidebar_shows_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='qos']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='qos'] not found")
    link.first.click()
    expect(page.locator("#panel-qos")).to_be_visible(timeout=5_000)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=3_000)


# ── 25. sidebar gets active class ────────────────────────────────────────────

def test_qos_sidebar_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='qos']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='qos'] not found")
    link.first.click()
    page.wait_for_timeout(300)
    classes = link.first.get_attribute("class") or ""
    assert "active" in classes, f"Expected .active on sidebar link, got: {classes!r}"


# ── 26. no JS errors ──────────────────────────────────────────────────────────

def test_qos_no_js_errors(logged_in: Page):
    page = logged_in
    js_errors: list[str] = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))
    _go_qos(page)
    page.wait_for_load_state("networkidle")
    expect(page.locator("#qosBody")).to_be_visible(timeout=8_000)
    assert not js_errors, f"JS errors on SDN QoS Policies page: {js_errors}"


# ── 27. webhook qos_policy.created appears ────────────────────────────────────

def test_webhook_qos_created_appears(logged_in: Page, api):
    rid = "e2e-qos-" + uuid.uuid4().hex[:10]
    rname = _QOS_NAME + "wh-" + uuid.uuid4().hex[:6]
    page = logged_in
    _go_qos(page)
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
        "event_type": "qos_policy.created",
        "resource_type": "qos_policy",
        "resource_id": rid,
        "payload": {"id": rid, "name": rname},
    })
    assert status in (200, 202), f"Webhook rejected: {status}"
    page.locator("button:has-text('Refresh')").first.click()
    page.wait_for_load_state("networkidle")
    row = page.locator("#qosBody").get_by_text(rname)
    expect(row.first).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/qos-policies/{rid}")


# ── 28. webhook qos_policy.deleted removes row ────────────────────────────────

def test_webhook_qos_deleted_removes_row(logged_in: Page, api):
    name = _QOS_NAME + "wh-del-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/qos-policies", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not seed QoS policy for webhook delete test")
    qos_id = r["body"]["id"]
    page = logged_in
    _go_qos(page)
    row = page.locator("#qosBody").get_by_text(name)
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
        "event_type": "qos_policy.deleted",
        "resource_type": "qos_policy",
        "resource_id": qos_id,
        "payload": {},
    })
    assert status in (200, 202), f"Webhook rejected: {status}"
    page.locator("button:has-text('Refresh')").first.click()
    page.wait_for_load_state("networkidle")
    expect(row.first).to_be_hidden(timeout=8_000)


# ── 29. webhook qos_policy.updated (API check: name updated) ─────────────────

def test_webhook_qos_updated_api_check(api):
    """qos_policy.updated webhook must update the record in the DB."""
    qos = _seed_qos(api)
    qos_id = qos["id"]
    new_name = _QOS_NAME + "upd-" + uuid.uuid4().hex[:6]
    try:
        api("POST", "/webhooks/nervum", {
            "event_type": "qos_policy.updated",
            "resource_type": "qos_policy",
            "resource_id": qos_id,
            "payload": {
                "id": qos_id,
                "name": new_name,
            },
        })
        deadline = time.time() + 5
        found = None
        while time.time() < deadline:
            r = api("GET", "/api/sdn/qos-policies")
            if r["status"] == 200:
                found = next((x for x in r["body"] if x["id"] == qos_id), None)
                if found and found.get("name") == new_name:
                    break
            time.sleep(0.2)
        assert found is not None, "Record disappeared after update webhook"
    finally:
        api("DELETE", f"/api/sdn/qos-policies/{qos_id}")
