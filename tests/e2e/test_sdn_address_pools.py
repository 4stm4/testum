# SPDX-License-Identifier: MIT
"""E2E: SDN Address Pools panel — Create form, API CRUD, table, webhooks."""
from __future__ import annotations

import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_POOL_NAME = "e2e-pool-"


def _go_pools(page: Page):
    page.goto(f"{BASE_URL}/sdn#pools")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page):
    page.locator(
        "#panel-pools button:has-text('Create'), #panel-pools button:has-text('+ Create')"
    ).first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


def _seed_pool(api, name: str | None = None, **extra) -> dict:
    """Seed an address pool via webhook. Polls until it lands in DB."""
    pool_id = "e2e-pool-" + uuid.uuid4().hex[:10]
    pool_name = name or (_POOL_NAME + uuid.uuid4().hex[:8])
    payload = {
        "event_type": "address_pool.created",
        "resource_type": "address_pool",
        "resource_id": pool_id,
        "project_id": extra.get("project_id"),
        "payload": {
            "id": pool_id,
            "name": pool_name,
            "project_id": extra.get("project_id"),
            "cidr": extra.get("cidr"),
        },
    }
    api("POST", "/webhooks/nervum", payload)
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/address-pools")
        if r["status"] == 200 and any(x["id"] == pool_id for x in r["body"]):
            break
        time.sleep(0.2)
    return {"id": pool_id, "name": pool_name}


# ── panel presence ────────────────────────────────────────────────────────────

def test_pools_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_pools(page)
    expect(page.locator("#panel-pools")).to_be_visible(timeout=8_000)


def test_pools_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_pools(page)
    expect(page.locator("#panel-routers")).to_be_hidden(timeout=5_000)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)


def test_pools_table_columns(logged_in: Page):
    page = logged_in
    _go_pools(page)
    headers = page.locator("#panel-pools thead th")
    texts = [headers.nth(i).inner_text().strip().upper() for i in range(headers.count())]
    for col in ("NAME", "CIDR"):
        assert any(col in t for t in texts), f"Column '{col}' not found in {texts}"


def test_pools_has_create_button(logged_in: Page):
    page = logged_in
    _go_pools(page)
    expect(
        page.locator(
            "#panel-pools button:has-text('Create'), #panel-pools button:has-text('+ Create')"
        ).first
    ).to_be_visible(timeout=5_000)


# ── modal open / close ────────────────────────────────────────────────────────

def test_create_modal_opens(logged_in: Page):
    page = logged_in
    _go_pools(page)
    _open_create_modal(page)
    expect(page.locator("#createModal")).to_be_visible(timeout=5_000)


def test_create_modal_title_contains_pool(logged_in: Page):
    page = logged_in
    _go_pools(page)
    _open_create_modal(page)
    title = page.locator("#createModalTitle").inner_text()
    assert "pool" in title.lower(), f"Modal title '{title}' does not mention pool"


def test_create_modal_has_name_field(logged_in: Page):
    page = logged_in
    _go_pools(page)
    _open_create_modal(page)
    expect(page.locator("#cf_name")).to_be_visible(timeout=3_000)


def test_create_modal_has_cidr_field(logged_in: Page):
    page = logged_in
    _go_pools(page)
    _open_create_modal(page)
    expect(page.locator("#cf_cidr")).to_be_visible(timeout=3_000)


def test_create_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_pools(page)
    _open_create_modal(page)
    page.locator("#createCancelBtn").click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)


def test_create_empty_name_keeps_modal_open(logged_in: Page):
    page = logged_in
    _go_pools(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill("")
    page.locator("#createSubmitBtn").click()
    expect(page.locator("#createModal")).to_be_visible(timeout=3_000)


# ── successful create ─────────────────────────────────────────────────────────

def test_create_pool_name_only(logged_in: Page, api):
    name = _POOL_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_pools(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/address-pools" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    pool_id = resp.value.json().get("id")
    if pool_id:
        api("DELETE", f"/api/sdn/address-pools/{pool_id}")


def test_create_pool_with_cidr(logged_in: Page, api):
    name = _POOL_NAME + uuid.uuid4().hex[:8]
    cidr = "10.1.0.0/24"
    page = logged_in
    _go_pools(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)
    page.locator("#cf_cidr").fill(cidr)

    with page.expect_response(
        lambda r: "/api/sdn/address-pools" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    pool_id = resp.value.json().get("id")
    if pool_id:
        r2 = api("GET", "/api/sdn/address-pools")
        pool = next((x for x in r2["body"] if x["id"] == pool_id), None)
        assert pool and pool["cidr"] == cidr
        api("DELETE", f"/api/sdn/address-pools/{pool_id}")


def test_create_pool_with_all_fields(api):
    name = _POOL_NAME + uuid.uuid4().hex[:8]
    pid = "proj-pool-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/address-pools", {
        "name": name,
        "project_id": pid,
        "cidr": "192.168.10.0/24",
    })
    assert r["status"] in (200, 201)
    pool_id = r["body"]["id"]
    r2 = api("GET", "/api/sdn/address-pools")
    pool = next((x for x in r2["body"] if x["id"] == pool_id), None)
    assert pool and pool["project_id"] == pid
    api("DELETE", f"/api/sdn/address-pools/{pool_id}")


def test_created_pool_appears_in_table(logged_in: Page, api):
    name = _POOL_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_pools(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/address-pools" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)
    pool_id = resp.value.json().get("id")

    row = page.locator("#poolsBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)
    if pool_id:
        api("DELETE", f"/api/sdn/address-pools/{pool_id}")


# ── delete from UI ────────────────────────────────────────────────────────────

def test_delete_pool_from_table(logged_in: Page, api):
    name = _POOL_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/address-pools", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create address pool via API")
    pool_id = r["body"]["id"]

    page = logged_in
    _go_pools(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#poolsBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#poolsBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/address-pools")
    assert pool_id not in [x["id"] for x in r2["body"]]


# ── full roundtrip ────────────────────────────────────────────────────────────

def test_create_and_delete_full_roundtrip(logged_in: Page):
    name = _POOL_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_pools(page)
    _open_create_modal(page)
    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/address-pools" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp:
        page.locator("#createSubmitBtn").click()

    assert resp.value.status in (200, 201)

    row = page.locator("#poolsBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#poolsBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_api_list_returns_list(api):
    r = api("GET", "/api/sdn/address-pools")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_create_minimal(api):
    name = _POOL_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/address-pools", {"name": name})
    assert r["status"] in (200, 201)
    assert r["body"].get("id")
    api("DELETE", f"/api/sdn/address-pools/{r['body']['id']}")


def test_api_create_missing_name_returns_422(api):
    r = api("POST", "/api/sdn/address-pools", {"cidr": "10.0.0.0/8"})
    assert r["status"] == 422


def test_api_delete_pool(api):
    r = api("POST", "/api/sdn/address-pools", {"name": _POOL_NAME + uuid.uuid4().hex[:8]})
    pool_id = r["body"]["id"]
    r2 = api("DELETE", f"/api/sdn/address-pools/{pool_id}")
    assert r2["status"] in (200, 204)
    r3 = api("GET", "/api/sdn/address-pools")
    assert pool_id not in [x["id"] for x in r3["body"]]


def test_api_delete_not_found(api):
    r = api("DELETE", "/api/sdn/address-pools/nonexistent-e2e-pool")
    assert r["status"] == 404


def test_api_filter_by_project_id(api):
    pid = "proj-pool-" + uuid.uuid4().hex[:6]
    r = api("POST", "/api/sdn/address-pools", {
        "name": _POOL_NAME + uuid.uuid4().hex[:8],
        "project_id": pid,
    })
    pool_id = r["body"]["id"]
    r2 = api("GET", f"/api/sdn/address-pools?project_id={pid}")
    assert r2["status"] == 200
    ids = [x["id"] for x in r2["body"]]
    assert pool_id in ids
    for x in r2["body"]:
        assert x["project_id"] == pid
    api("DELETE", f"/api/sdn/address-pools/{pool_id}")


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_sidebar_link_activates_pools_hash(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='pools']")
    if link.count() == 0:
        pytest.skip("Sidebar pools link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "pools" in page.url


def test_sidebar_link_shows_pools_panel(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='pools']")
    if link.count() == 0:
        pytest.skip("Sidebar pools link not found")
    link.first.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#panel-pools")).to_be_visible(timeout=5_000)


def test_sidebar_pools_link_gets_active_class(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='pools']")
    if link.count() == 0:
        pytest.skip("Sidebar pools link not found")
    link.first.click()
    page.wait_for_timeout(300)
    assert "active" in (link.first.get_attribute("class") or "")


# ── no JS errors ──────────────────────────────────────────────────────────────

def test_pools_no_js_errors(logged_in: Page):
    page = logged_in
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    _go_pools(page)
    page.wait_for_load_state("networkidle")
    assert [e for e in errors if "Uncaught" in e or "TypeError" in e] == []


# ── Webhook → UI integration ──────────────────────────────────────────────────

def test_webhook_pool_created_appears_in_table(logged_in: Page, api):
    page = logged_in
    _go_pools(page)
    page.wait_for_load_state("networkidle")

    info = _seed_pool(api)
    page.reload()
    page.wait_for_load_state("networkidle")

    expect(
        page.locator("#poolsBody").get_by_text(info["name"]).first
    ).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/sdn/address-pools/{info['id']}")


def test_webhook_pool_deleted_removes_row(logged_in: Page, api):
    info = _seed_pool(api)
    page = logged_in
    _go_pools(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#poolsBody").get_by_text(info["name"])
    expect(row.first).to_be_visible(timeout=8_000)

    api("POST", "/webhooks/nervum", {
        "event_type": "address_pool.deleted",
        "resource_type": "address_pool",
        "resource_id": info["id"],
        "payload": {},
    })
    page.reload()
    page.wait_for_load_state("networkidle")
    expect(row.first).to_be_hidden(timeout=8_000)


def test_webhook_pool_updated(api):
    """address_pool.updated reflects changed cidr in replica."""
    info = _seed_pool(api, cidr="10.2.0.0/24")
    new_cidr = "10.3.0.0/24"
    api("POST", "/webhooks/nervum", {
        "event_type": "address_pool.updated",
        "resource_type": "address_pool",
        "resource_id": info["id"],
        "payload": {
            "id": info["id"],
            "name": info["name"],
            "cidr": new_cidr,
        },
    })
    deadline = time.time() + 5
    while time.time() < deadline:
        r = api("GET", "/api/sdn/address-pools")
        pool = next((x for x in r["body"] if x["id"] == info["id"]), None)
        if pool and pool.get("cidr") == new_cidr:
            break
        time.sleep(0.2)
    r = api("GET", "/api/sdn/address-pools")
    pool = next((x for x in r["body"] if x["id"] == info["id"]), None)
    assert pool and pool.get("cidr") == new_cidr
    api("DELETE", f"/api/sdn/address-pools/{info['id']}")
