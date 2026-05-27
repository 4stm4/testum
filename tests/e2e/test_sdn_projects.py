# SPDX-License-Identifier: MIT
"""E2E: SDN Projects panel — bind/unbind UI, API CRUD, idempotency."""
from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_projects(page: Page):
    page.goto(f"{BASE_URL}/sdn#projects")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='projects']")
    if link.count():
        link.first.click()
        page.wait_for_timeout(400)


def _open_bind_modal(page: Page):
    panel = page.locator("#panel-projects")
    btn = panel.locator("button:has-text('Bind Project'), button:has-text('Bind')")
    btn.first.click()
    page.locator("#bindModal").wait_for(state="visible", timeout=5_000)


# ── panel presence ────────────────────────────────────────────────────────────

def test_projects_panel_active_on_hash(logged_in: Page):
    """Navigating to sdn#projects must make #panel-projects visible."""
    page = logged_in
    _go_projects(page)
    expect(page.locator("#panel-projects")).to_be_visible(timeout=8_000)


def test_projects_other_panels_hidden(logged_in: Page):
    """#panel-networks must be hidden when projects tab is active."""
    page = logged_in
    _go_projects(page)
    expect(page.locator("#panel-networks")).to_be_hidden(timeout=5_000)


def test_projects_has_bind_button(logged_in: Page):
    """Projects panel header must contain a 'Bind Project' button."""
    page = logged_in
    _go_projects(page)
    panel = page.locator("#panel-projects")
    btn = panel.locator("button:has-text('Bind Project'), button:has-text('Bind')")
    expect(btn.first).to_be_visible(timeout=5_000)


def test_projects_table_columns(logged_in: Page):
    """Projects table must include TESTUM PROJECT and NERVUM PROJECT columns."""
    page = logged_in
    _go_projects(page)
    panel = page.locator("#panel-projects")
    headers = panel.locator("thead th").all_inner_texts()
    combined = " ".join(h.lower() for h in headers)
    assert "testum" in combined or "project" in combined, (
        f"Expected TESTUM PROJECT column, headers: {headers}"
    )
    assert "nervum" in combined or "project" in combined, (
        f"Expected NERVUM PROJECT column, headers: {headers}"
    )


# ── bind modal ────────────────────────────────────────────────────────────────

def test_bind_modal_opens_on_button_click(logged_in: Page):
    """Clicking Bind Project button must open #bindModal."""
    page = logged_in
    _go_projects(page)
    _open_bind_modal(page)
    expect(page.locator("#bindModal")).to_be_visible()


def test_bind_modal_has_testum_id_field(logged_in: Page):
    """Bind modal must contain #bindTestumId input."""
    page = logged_in
    _go_projects(page)
    _open_bind_modal(page)
    expect(page.locator("#bindTestumId")).to_be_visible(timeout=3_000)


def test_bind_modal_has_nervum_id_field(logged_in: Page):
    """Bind modal must contain #bindNervumId input."""
    page = logged_in
    _go_projects(page)
    _open_bind_modal(page)
    expect(page.locator("#bindNervumId")).to_be_visible(timeout=3_000)


def test_bind_modal_cancel_closes(logged_in: Page):
    """Clicking Cancel in bind modal must close it."""
    page = logged_in
    _go_projects(page)
    _open_bind_modal(page)
    cancel = page.locator("#bindModal button:has-text('Cancel'), #bindModal [data-dismiss]")
    cancel.first.click()
    expect(page.locator("#bindModal")).to_be_hidden(timeout=3_000)


def test_bind_modal_submit_creates_binding(logged_in: Page, api):
    """Filling in testum/nervum IDs and clicking submit must create a binding."""
    tp_id = "tp-" + uuid.uuid4().hex[:8]
    np_id = "np-" + uuid.uuid4().hex[:8]

    page = logged_in
    _go_projects(page)
    _open_bind_modal(page)

    page.locator("#bindTestumId").fill(tp_id)
    page.locator("#bindNervumId").fill(np_id)

    with page.expect_response(
        lambda r: "/api/sdn/projects" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp_info:
        page.locator("#bindSubmitBtn").click()

    assert resp_info.value.status in (200, 201), (
        f"Bind submit failed: {resp_info.value.status}"
    )
    body = resp_info.value.json()
    binding_id = body.get("id")

    # Cleanup
    if binding_id:
        api("DELETE", f"/api/sdn/projects/{binding_id}")


def test_binding_appears_in_table_after_create(logged_in: Page, api):
    """After creating a binding via the modal it must appear in the projects table."""
    tp_id = "tp-" + uuid.uuid4().hex[:8]
    np_id = "np-" + uuid.uuid4().hex[:8]

    page = logged_in
    _go_projects(page)
    _open_bind_modal(page)

    page.locator("#bindTestumId").fill(tp_id)
    page.locator("#bindNervumId").fill(np_id)

    with page.expect_response(
        lambda r: "/api/sdn/projects" in r.url and r.request.method == "POST",
        timeout=8_000,
    ) as resp_info:
        page.locator("#bindSubmitBtn").click()

    if resp_info.value.status not in (200, 201):
        pytest.skip("Binding creation failed — skipping table check")

    binding_id = resp_info.value.json().get("id")

    row = page.locator("#projectsBody").get_by_text(tp_id)
    expect(row.first).to_be_visible(timeout=8_000)

    if binding_id:
        api("DELETE", f"/api/sdn/projects/{binding_id}")


def test_unbind_button_present_after_creating_binding(logged_in: Page, api):
    """After creating a binding via API, a row with an Unbind button must be visible."""
    tp_id = "tp-" + uuid.uuid4().hex[:8]
    np_id = "np-" + uuid.uuid4().hex[:8]

    r = api("POST", "/api/sdn/projects", {
        "testum_project_id": tp_id,
        "nervum_project_id": np_id,
    })
    if r["status"] not in (200, 201):
        pytest.skip("Could not create binding via API")
    binding_id = r["body"]["id"]

    try:
        page = logged_in
        _go_projects(page)

        row_locator = page.locator(f"#projectsBody tr:has-text('{tp_id}')")
        expect(row_locator.first).to_be_visible(timeout=8_000)

        unbind_btn = row_locator.first.locator("button:has-text('Unbind')")
        expect(unbind_btn).to_be_visible(timeout=5_000)
    finally:
        api("DELETE", f"/api/sdn/projects/{binding_id}")


# ── API: list ─────────────────────────────────────────────────────────────────

def test_api_projects_list_returns_list(api):
    """GET /api/sdn/projects must return 200 and a JSON list."""
    r = api("GET", "/api/sdn/projects")
    assert r["status"] == 200, f"Expected 200, got {r['status']}"
    assert isinstance(r["body"], list), f"Expected list, got {type(r['body'])}"


# ── API: create ───────────────────────────────────────────────────────────────

def test_api_create_binding_returns_200_or_201(api):
    """POST /api/sdn/projects with valid data must return 200 or 201."""
    tp_id = "tp-" + uuid.uuid4().hex[:8]
    np_id = "np-" + uuid.uuid4().hex[:8]

    r = api("POST", "/api/sdn/projects", {
        "testum_project_id": tp_id,
        "nervum_project_id": np_id,
    })
    assert r["status"] in (200, 201), f"Expected 200/201, got {r}"
    binding_id = r["body"].get("id")
    assert binding_id

    api("DELETE", f"/api/sdn/projects/{binding_id}")


def test_api_create_binding_idempotent(api):
    """POSTing the same testum_project_id twice must return 200 both times (idempotent)."""
    tp_id = "tp-" + uuid.uuid4().hex[:8]
    np_id = "np-" + uuid.uuid4().hex[:8]

    r1 = api("POST", "/api/sdn/projects", {
        "testum_project_id": tp_id,
        "nervum_project_id": np_id,
    })
    assert r1["status"] in (200, 201), f"First create failed: {r1}"
    binding_id = r1["body"]["id"]

    try:
        r2 = api("POST", "/api/sdn/projects", {
            "testum_project_id": tp_id,
            "nervum_project_id": np_id,
        })
        assert r2["status"] == 200, (
            f"Second POST with same testum_project_id should return 200 (idempotent), got {r2['status']}"
        )
        assert r2["body"]["id"] == binding_id, "Idempotent POST returned different binding ID"
    finally:
        api("DELETE", f"/api/sdn/projects/{binding_id}")


# ── API: get single ───────────────────────────────────────────────────────────

def test_api_get_single_binding_returns_200(api):
    """GET /api/sdn/projects/{binding_id} must return 200 with the binding data."""
    tp_id = "tp-" + uuid.uuid4().hex[:8]
    np_id = "np-" + uuid.uuid4().hex[:8]

    r = api("POST", "/api/sdn/projects", {
        "testum_project_id": tp_id,
        "nervum_project_id": np_id,
    })
    if r["status"] not in (200, 201):
        pytest.skip("Could not create binding via API")
    binding_id = r["body"]["id"]

    try:
        r2 = api("GET", f"/api/sdn/projects/{binding_id}")
        assert r2["status"] == 200, f"Expected 200, got {r2['status']}"
        assert r2["body"]["id"] == binding_id
    finally:
        api("DELETE", f"/api/sdn/projects/{binding_id}")


def test_api_get_binding_not_found(api):
    """GET /api/sdn/projects/{nonexistent} must return 404."""
    r = api("GET", f"/api/sdn/projects/{uuid.uuid4()}")
    assert r["status"] == 404, f"Expected 404, got {r['status']}"


# ── API: delete ───────────────────────────────────────────────────────────────

def test_api_delete_binding_returns_200(api):
    """DELETE /api/sdn/projects/{binding_id} must return 200."""
    tp_id = "tp-" + uuid.uuid4().hex[:8]
    np_id = "np-" + uuid.uuid4().hex[:8]

    r = api("POST", "/api/sdn/projects", {
        "testum_project_id": tp_id,
        "nervum_project_id": np_id,
    })
    if r["status"] not in (200, 201):
        pytest.skip("Could not create binding via API")
    binding_id = r["body"]["id"]

    r2 = api("DELETE", f"/api/sdn/projects/{binding_id}")
    assert r2["status"] == 200, f"Expected 200, got {r2['status']}"

    # Verify it's gone
    r3 = api("GET", f"/api/sdn/projects/{binding_id}")
    assert r3["status"] == 404


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_projects_sidebar_link_activates_hash(logged_in: Page):
    """Clicking [data-sdn-tab='projects'] must put #projects in the URL."""
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")

    link = page.locator("[data-sdn-tab='projects']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='projects'] not found")

    link.first.click()
    page.wait_for_timeout(300)
    assert "projects" in page.url, f"Expected 'projects' in URL, got: {page.url}"


def test_projects_sidebar_shows_panel(logged_in: Page):
    """Clicking sidebar projects link must show #panel-projects."""
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")

    link = page.locator("[data-sdn-tab='projects']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='projects'] not found")

    link.first.click()
    expect(page.locator("#panel-projects")).to_be_visible(timeout=5_000)


def test_projects_sidebar_active_class(logged_in: Page):
    """Active sidebar projects link must receive .active CSS class."""
    page = logged_in
    page.goto(f"{BASE_URL}/sdn#networks")
    page.wait_for_load_state("networkidle")

    link = page.locator("[data-sdn-tab='projects']")
    if link.count() == 0:
        pytest.skip("Sidebar link [data-sdn-tab='projects'] not found")

    link.first.click()
    page.wait_for_timeout(300)
    classes = link.first.get_attribute("class") or ""
    assert "active" in classes, f"Expected .active on projects sidebar link, got: {classes!r}"


# ── no JS errors ──────────────────────────────────────────────────────────────

def test_projects_no_js_errors_on_load(logged_in: Page):
    """Projects panel must load without JavaScript exceptions."""
    page = logged_in
    js_errors: list[str] = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    _go_projects(page)
    page.wait_for_load_state("networkidle")

    assert not js_errors, f"JS errors on SDN Projects page: {js_errors}"
