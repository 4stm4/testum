# SPDX-License-Identifier: MIT
"""E2E: SDN Networks panel — API CRUD, Create form, table, sidebar, webhooks."""
from __future__ import annotations

import json
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL

_NET_NAME = "e2e-net-"


def _go_networks(page: Page):
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")


def _open_create_modal(page: Page):
    panel = page.locator("#panel-networks")
    btn = panel.locator("button:has-text('Create'), button:has-text('+ Create')")
    btn.first.click()
    page.locator("#createModal").wait_for(state="visible", timeout=5_000)


# ── panel presence ────────────────────────────────────────────────────────────

def test_networks_panel_active_on_hash(logged_in: Page):
    page = logged_in
    _go_networks(page)
    panel = page.locator("#panel-networks")
    expect(panel).to_be_visible(timeout=8_000)


def test_networks_other_panels_hidden(logged_in: Page):
    page = logged_in
    _go_networks(page)
    hidden = page.locator("#panel-nodes")
    expect(hidden).to_be_hidden(timeout=5_000)


def test_networks_table_columns(logged_in: Page):
    page = logged_in
    _go_networks(page)
    panel = page.locator("#panel-networks")
    headers = panel.locator("thead th").all_inner_texts()
    assert any("name" in h.lower() for h in headers), f"NAME column missing: {headers}"


def test_networks_create_button_visible(logged_in: Page):
    page = logged_in
    _go_networks(page)
    panel = page.locator("#panel-networks")
    btn = panel.locator("button:has-text('Create'), button:has-text('+ Create')")
    expect(btn.first).to_be_visible(timeout=5_000)


# ── modal open / close ────────────────────────────────────────────────────────

def test_create_modal_opens(logged_in: Page):
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)
    modal = page.locator("#createModal")
    expect(modal).to_be_visible()


def test_create_modal_title(logged_in: Page):
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)
    title = page.locator("#createModalTitle").inner_text()
    assert "network" in title.lower(), f"Unexpected modal title: {title!r}"


def test_create_modal_has_name_field(logged_in: Page):
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)
    name_input = page.locator("#cf_name")
    expect(name_input).to_be_visible()


def test_create_modal_has_all_fields(logged_in: Page):
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)
    for field_id in ("cf_name", "cf_type", "cf_project_id", "cf_vni", "cf_mtu"):
        expect(page.locator(f"#{field_id}")).to_be_visible(
            timeout=3_000
        ), f"Field #{field_id} not visible"


def test_create_modal_name_focused(logged_in: Page):
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)
    focused = page.evaluate("document.activeElement?.id")
    assert focused == "cf_name", f"Expected cf_name to be focused, got: {focused!r}"


def test_create_modal_cancel_closes(logged_in: Page):
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)
    cancel = page.locator("#createModal button:has-text('Cancel')")
    cancel.first.click()
    expect(page.locator("#createModal")).to_be_hidden(timeout=3_000)


def test_create_modal_backdrop_click_closes(logged_in: Page):
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)
    # Click the backdrop (outside the modal-box) by clicking top-left corner
    page.locator("#createModal").click(position={"x": 5, "y": 5})
    expect(page.locator("#createModal")).to_be_hidden(timeout=3_000)


# ── client-side validation ────────────────────────────────────────────────────

def test_create_empty_name_shows_error(logged_in: Page):
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)
    # Submit without filling Name
    page.locator("#createSubmitBtn").click()
    # Modal must stay open (no API call made)
    expect(page.locator("#createModal")).to_be_visible(timeout=2_000)


def test_create_empty_name_no_api_call(logged_in: Page):
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)
    api_called = []
    page.on("request", lambda r: api_called.append(r.url) if "/api/sdn/networks" in r.url else None)
    page.locator("#createSubmitBtn").click()
    page.wait_for_timeout(500)
    assert not api_called, "API should not be called when name is empty"


# ── successful create ─────────────────────────────────────────────────────────

def test_create_network_name_only(logged_in: Page, api):
    name = _NET_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)

    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/networks" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp_info:
        page.locator("#createSubmitBtn").click()

    assert resp_info.value.status in (200, 201), f"Create failed: {resp_info.value.status}"
    created_id = resp_info.value.json().get("id")

    # Modal closes on success
    expect(page.locator("#createModal")).to_be_hidden(timeout=5_000)

    # Cleanup
    if created_id:
        api("DELETE", f"/api/sdn/networks/{created_id}")


def test_create_network_all_fields(logged_in: Page, api):
    name = _NET_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)

    page.locator("#cf_name").fill(name)
    page.locator("#cf_type").fill("vxlan")
    page.locator("#cf_project_id").fill("proj-e2e")
    page.locator("#cf_vni").fill("42")
    page.locator("#cf_mtu").fill("1400")

    with page.expect_response(
        lambda r: "/api/sdn/networks" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp_info:
        page.locator("#createSubmitBtn").click()

    assert resp_info.value.status in (200, 201)
    body = resp_info.value.json()
    created_id = body.get("id")

    # Cleanup
    if created_id:
        api("DELETE", f"/api/sdn/networks/{created_id}")


def test_create_network_vni_sent_as_number(logged_in: Page, api):
    """VNI must be a JSON number, not a string."""
    name = _NET_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)

    page.locator("#cf_name").fill(name)
    page.locator("#cf_vni").fill("100")

    sent_body = {}

    def capture(req):
        if "/api/sdn/networks" in req.url and req.method == "POST":
            import json
            try:
                sent_body.update(json.loads(req.post_data or "{}"))
            except Exception:
                pass

    page.on("request", capture)

    with page.expect_response(
        lambda r: "/api/sdn/networks" in r.url and r.request.method == "POST",
        timeout=8_000,
    ):
        page.locator("#createSubmitBtn").click()

    assert isinstance(sent_body.get("vni"), (int, float)), (
        f"vni should be a number, got {type(sent_body.get('vni'))}: {sent_body}"
    )

    # Cleanup
    r = api("GET", "/api/sdn/networks")
    for net in r.get("body", []):
        if net.get("name") == name:
            api("DELETE", f"/api/sdn/networks/{net['id']}")
            break


def test_create_network_empty_optional_fields_omitted(logged_in: Page, api):
    """Empty optional fields must not appear in the POST body."""
    name = _NET_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)

    page.locator("#cf_name").fill(name)
    # Leave type, project_id, vni, mtu blank

    sent_body = {}

    def capture(req):
        if "/api/sdn/networks" in req.url and req.method == "POST":
            import json
            try:
                sent_body.update(json.loads(req.post_data or "{}"))
            except Exception:
                pass

    page.on("request", capture)

    with page.expect_response(
        lambda r: "/api/sdn/networks" in r.url and r.request.method == "POST",
        timeout=8_000,
    ):
        page.locator("#createSubmitBtn").click()

    for optional in ("type", "project_id", "vni", "mtu"):
        assert optional not in sent_body, f"Empty field {optional!r} should not be in payload"

    # Cleanup
    r = api("GET", "/api/sdn/networks")
    for net in r.get("body", []):
        if net.get("name") == name:
            api("DELETE", f"/api/sdn/networks/{net['id']}")
            break


# ── table update after create ─────────────────────────────────────────────────

def test_created_network_appears_in_table(logged_in: Page, api):
    name = _NET_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)

    page.locator("#cf_name").fill(name)

    with page.expect_response(
        lambda r: "/api/sdn/networks" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp_info:
        page.locator("#createSubmitBtn").click()

    created_id = resp_info.value.json().get("id")

    # Table should reload automatically — row must appear
    row = page.locator(f"#networksBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    if created_id:
        api("DELETE", f"/api/sdn/networks/{created_id}")


# ── delete from UI ────────────────────────────────────────────────────────────

def test_delete_network_from_table(logged_in: Page, api):
    name = _NET_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/networks", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not create network via API")
    net_id = r["body"]["id"]

    page = logged_in
    _go_networks(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#networksBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#networksBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)
    r2 = api("GET", "/api/sdn/networks")
    assert net_id not in [n["id"] for n in r2["body"]], "Network still in DB after UI delete"


# ── full roundtrip ────────────────────────────────────────────────────────────

def test_create_and_delete_full_roundtrip(logged_in: Page):
    """Create via UI form → verify in table → delete via UI → verify gone."""
    name = _NET_NAME + uuid.uuid4().hex[:8]
    page = logged_in
    _go_networks(page)
    _open_create_modal(page)

    page.locator("#cf_name").fill(name)
    page.locator("#cf_type").fill("flat")

    with page.expect_response(
        lambda r: "/api/sdn/networks" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as create_resp:
        page.locator("#createSubmitBtn").click()

    assert create_resp.value.status in (200, 201)
    net_id = create_resp.value.json().get("id")

    row = page.locator("#networksBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    del_btn = page.locator(f"#networksBody tr:has-text('{name}') button")
    page.on("dialog", lambda d: d.accept())
    del_btn.first.click()

    expect(row.first).to_be_hidden(timeout=15_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_api_create_network_minimal(api):
    """POST with only name must be accepted."""
    r = api("POST", "/api/sdn/networks", {"name": _NET_NAME + uuid.uuid4().hex[:8]})
    assert r["status"] in (200, 201), f"Expected 201, got {r}"
    net_id = r["body"].get("id")
    assert net_id
    api("DELETE", f"/api/sdn/networks/{net_id}")


def test_api_create_network_all_fields(api):
    """POST with all optional fields must be accepted."""
    name = _NET_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/networks", {
        "name": name, "type": "vxlan",
        "project_id": "proj-e2e", "vni": 999, "mtu": 1400,
    })
    assert r["status"] in (200, 201), f"Expected 201, got {r}"
    api("DELETE", f"/api/sdn/networks/{r['body']['id']}")


def test_api_create_network_missing_name_returns_error(api):
    """POST without name must return 4xx."""
    r = api("POST", "/api/sdn/networks", {"type": "vxlan"})
    assert r["status"] in (400, 422), f"Expected 422, got {r}"


def test_api_delete_network_not_found(api):
    """DELETE on unknown ID must return 404."""
    r = api("DELETE", f"/api/sdn/networks/{uuid.uuid4()}")
    assert r["status"] == 404, f"Expected 404, got {r}"


def test_api_network_full_lifecycle(api):
    """Create → appears in list → delete → gone from list."""
    name = _NET_NAME + uuid.uuid4().hex[:8]

    r = api("POST", "/api/sdn/networks", {"name": name})
    assert r["status"] in (200, 201)
    net_id = r["body"]["id"]

    r2 = api("GET", "/api/sdn/networks")
    assert r2["status"] == 200
    ids = [n["id"] for n in r2["body"]]
    assert net_id in ids, "Created network not found in list"

    r3 = api("DELETE", f"/api/sdn/networks/{net_id}")
    assert r3["status"] in (200, 204)

    r4 = api("GET", "/api/sdn/networks")
    ids_after = [n["id"] for n in r4["body"]]
    assert net_id not in ids_after, "Deleted network still in list"


def test_api_project_filter_isolates_correctly(api):
    """Network with project_id=A must NOT appear when filtering by project_id=B."""
    name = _NET_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/networks", {"name": name, "project_id": "proj-filter-a"})
    assert r["status"] in (200, 201)
    net_id = r["body"]["id"]

    try:
        r2 = api("GET", "/api/sdn/networks?project_id=proj-filter-b")
        assert r2["status"] == 200
        ids = [n["id"] for n in r2["body"]]
        assert net_id not in ids, "Network leaked into wrong project filter"
    finally:
        api("DELETE", f"/api/sdn/networks/{net_id}")


def test_api_project_filter_returns_own(api):
    """Network with project_id=X must appear when filtering by the same project_id."""
    name = _NET_NAME + uuid.uuid4().hex[:8]
    r = api("POST", "/api/sdn/networks", {"name": name, "project_id": "proj-filter-own"})
    assert r["status"] in (200, 201)
    net_id = r["body"]["id"]

    try:
        r2 = api("GET", "/api/sdn/networks?project_id=proj-filter-own")
        assert r2["status"] == 200
        ids = [n["id"] for n in r2["body"]]
        assert net_id in ids, "Network not found with its own project_id filter"
    finally:
        api("DELETE", f"/api/sdn/networks/{net_id}")


def test_api_list_includes_two_created(api):
    """After creating two networks both must appear in the unfiltered list."""
    name_a = _NET_NAME + uuid.uuid4().hex[:8]
    name_b = _NET_NAME + uuid.uuid4().hex[:8]
    ra = api("POST", "/api/sdn/networks", {"name": name_a})
    rb = api("POST", "/api/sdn/networks", {"name": name_b})
    assert ra["status"] in (200, 201)
    assert rb["status"] in (200, 201)
    id_a, id_b = ra["body"]["id"], rb["body"]["id"]

    try:
        r = api("GET", "/api/sdn/networks")
        assert r["status"] == 200
        ids = [n["id"] for n in r["body"]]
        assert id_a in ids and id_b in ids, f"Not both networks in list: {ids}"
    finally:
        api("DELETE", f"/api/sdn/networks/{id_a}")
        api("DELETE", f"/api/sdn/networks/{id_b}")


def test_api_list_returns_list(api):
    """GET /api/sdn/networks must always return a JSON array."""
    r = api("GET", "/api/sdn/networks")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


# ── UI: sidebar navigation ────────────────────────────────────────────────────

def test_sidebar_link_activates_networks_hash(logged_in: Page):
    """Clicking [data-sdn-tab='networks'] in sidebar must put #networks in the URL."""
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#nodes")
    page.wait_for_load_state("networkidle")

    link = page.locator("[data-sdn-tab='networks']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='networks'] not found")

    link.first.click()
    page.wait_for_timeout(300)
    assert "#networks" in page.url, f"Expected #networks in URL, got: {page.url}"


def test_sidebar_link_shows_networks_panel(logged_in: Page):
    """Clicking sidebar Networks link must show panel-networks and hide panel-nodes."""
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#nodes")
    page.wait_for_load_state("networkidle")

    link = page.locator("[data-sdn-tab='networks']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='networks'] not found")

    link.first.click()
    expect(page.locator("#panel-networks")).to_be_visible(timeout=5_000)
    expect(page.locator("#panel-nodes")).to_be_hidden(timeout=3_000)


def test_sidebar_link_gets_active_class(logged_in: Page):
    """Active sidebar link must receive .active CSS class."""
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#nodes")
    page.wait_for_load_state("networkidle")

    link = page.locator("[data-sdn-tab='networks']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='networks'] not found")

    link.first.click()
    page.wait_for_timeout(300)
    classes = link.first.get_attribute("class") or ""
    assert "active" in classes, f"Expected .active on sidebar link, got: {classes!r}"


# ── UI: empty state ───────────────────────────────────────────────────────────

def test_networks_empty_state_no_js_error(logged_in: Page):
    """Page must load without JS exceptions regardless of whether networks exist."""
    page = logged_in
    js_errors: list[str] = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    _go_networks(page)
    page.wait_for_load_state("networkidle")

    expect(page.locator("#networksBody")).to_be_visible(timeout=8_000)
    assert not js_errors, f"JS errors on SDN Networks page: {js_errors}"


def test_networks_empty_row_shows_message(logged_in: Page, api):
    """When the table is empty an empty-state cell must be shown, not a blank tbody."""
    # Clean up any e2e networks so the table is empty
    r = api("GET", "/api/sdn/networks")
    if r["status"] == 200:
        for net in r["body"]:
            if net.get("name", "").startswith("e2e-"):
                api("DELETE", f"/api/sdn/networks/{net['id']}")

    r2 = api("GET", "/api/sdn/networks")
    if r2["status"] == 200 and len(r2["body"]) > 0:
        pytest.skip("Non-e2e networks exist — cannot test empty state")

    page = logged_in
    _go_networks(page)
    page.wait_for_load_state("networkidle")

    empty = page.locator("#networksBody .empty-row, #networksBody td:has-text('No')")
    expect(empty.first).to_be_visible(timeout=8_000)


# ── Webhook → UI integration ─────────────────────────────────────────────────

def _send_webhook(page: Page, payload: dict) -> int:
    body = json.dumps(payload)
    return page.evaluate(f"""
    async () => {{
        const r = await fetch('/webhooks/nervum', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: {body!r},
        }});
        return r.status;
    }}
    """)


def test_webhook_network_created_appears_in_table(logged_in: Page, api):
    """network.created webhook must persist the record so it shows after UI refresh."""
    net_id = "wh-net-" + uuid.uuid4().hex[:8]
    name   = _NET_NAME + "wh-" + uuid.uuid4().hex[:6]

    page = logged_in
    _go_networks(page)
    page.wait_for_load_state("networkidle")

    status = _send_webhook(page, {
        "schema_version": 2,
        "event_id": int(uuid.uuid4().int % 1_000_000),
        "event_type": "network.created",
        "resource_type": "network",
        "resource_id": net_id,
        "payload": {"name": name, "type": "vxlan"},
    })
    assert status in (200, 202), f"Webhook rejected: {status}"

    page.locator("button:has-text('Refresh')").first.click()
    page.wait_for_load_state("networkidle")

    row = page.locator("#networksBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    api("DELETE", f"/api/sdn/networks/{net_id}")


def test_webhook_network_deleted_removes_row(logged_in: Page, api):
    """network.deleted webhook must remove the record so it's gone after UI refresh."""
    name = _NET_NAME + "wh-del-" + uuid.uuid4().hex[:6]

    r = api("POST", "/api/sdn/networks", {"name": name})
    if r["status"] not in (200, 201):
        pytest.skip("Could not seed network for webhook delete test")
    net_id = r["body"]["id"]

    page = logged_in
    _go_networks(page)
    page.wait_for_load_state("networkidle")

    row = page.locator("#networksBody").get_by_text(name)
    expect(row.first).to_be_visible(timeout=8_000)

    status = _send_webhook(page, {
        "schema_version": 2,
        "event_id": int(uuid.uuid4().int % 1_000_000),
        "event_type": "network.deleted",
        "resource_type": "network",
        "resource_id": net_id,
        "payload": {},
    })
    assert status in (200, 202), f"Webhook rejected: {status}"

    page.locator("button:has-text('Refresh')").first.click()
    page.wait_for_load_state("networkidle")

    expect(row.first).to_be_hidden(timeout=8_000)
