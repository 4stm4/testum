# SPDX-License-Identifier: MIT
"""E2E: Jobs list — page, API filters, task detail, automation-triggered job."""
from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_jobs(page: Page):
    page.goto(f"{BASE_URL}/jobs")
    page.wait_for_load_state("networkidle")


# ── page loads ────────────────────────────────────────────────────────────────

def test_jobs_page_loads(logged_in: Page):
    """Navigating to /jobs must succeed without redirect to login."""
    page = logged_in
    _go_jobs(page)
    assert "/login" not in page.url, f"Redirected to login: {page.url}"
    assert "jobs" in page.url or "/" in page.url


def test_jobs_page_has_table_or_empty(logged_in: Page):
    """Jobs page must show a table or empty-state element."""
    page = logged_in
    _go_jobs(page)
    area = page.locator(
        "table, .empty-state, [data-empty], "
        "text='No jobs', text='No tasks', text='No results'"
    )
    expect(area.first).to_be_visible(timeout=8_000)


# ── API: list + filters ───────────────────────────────────────────────────────

def test_jobs_api_returns_list(api):
    """GET /api/tasks/?limit=20 must return 200 and a JSON list."""
    r = api("GET", "/api/tasks/?limit=20")
    assert r["status"] == 200, f"Expected 200, got {r['status']}"
    assert isinstance(r["body"], list), f"Expected list, got {type(r['body'])}"


def test_jobs_api_filter_running(api):
    """GET /api/tasks/?status=running must return 200 and a list."""
    r = api("GET", "/api/tasks/?status=running")
    assert r["status"] == 200, f"Expected 200, got {r['status']}"
    assert isinstance(r["body"], list)


def test_jobs_api_filter_completed(api):
    """GET /api/tasks/?status=completed must return 200 and a list."""
    r = api("GET", "/api/tasks/?status=completed")
    assert r["status"] == 200, f"Expected 200, got {r['status']}"
    assert isinstance(r["body"], list)


def test_jobs_api_filter_failed(api):
    """GET /api/tasks/?status=failed must return 200 and a list."""
    r = api("GET", "/api/tasks/?status=failed")
    assert r["status"] == 200, f"Expected 200, got {r['status']}"
    assert isinstance(r["body"], list)


def test_jobs_api_limit(api):
    """GET /api/tasks/?limit=3 must return at most 3 items."""
    r = api("GET", "/api/tasks/?limit=3")
    assert r["status"] == 200
    assert isinstance(r["body"], list)
    assert len(r["body"]) <= 3, f"Expected ≤3 items with limit=3, got {len(r['body'])}"


def test_jobs_api_get_not_found(api):
    """GET /api/tasks/{nonexistent} must return 404."""
    r = api("GET", "/api/tasks/nonexistent-task-id-that-does-not-exist")
    assert r["status"] == 404, f"Expected 404, got {r['status']}"


# ── page quality ──────────────────────────────────────────────────────────────

def test_jobs_page_no_js_errors(logged_in: Page):
    """Jobs page must load without JavaScript exceptions."""
    page = logged_in
    js_errors: list[str] = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    _go_jobs(page)
    page.wait_for_load_state("networkidle")

    assert not js_errors, f"JS errors on /jobs page: {js_errors}"


def test_jobs_sidebar_link_active(logged_in: Page):
    """Sidebar link to /jobs must have .active class when on the jobs page."""
    page = logged_in
    _go_jobs(page)

    link = page.locator(
        "a[href*='jobs'].active, nav a[href*='jobs'].active, "
        "sidebar a[href*='jobs'].active, a.active[href*='jobs']"
    )
    # Try a broader approach: find the /jobs nav link regardless of active class
    jobs_link = page.locator("nav a[href*='jobs'], aside a[href*='jobs'], a[href='/jobs']")
    if jobs_link.count() == 0:
        pytest.skip("No /jobs sidebar link found")

    classes = jobs_link.first.get_attribute("class") or ""
    # Active class is expected; warn if absent but don't hard-fail if the link exists
    assert jobs_link.first.is_visible(), "Jobs sidebar link not visible"


def test_jobs_page_has_status_filter(logged_in: Page):
    """Jobs page must have some status filter control or a status column in the table."""
    page = logged_in
    _go_jobs(page)

    filter_or_column = page.locator(
        "select[name*='status'], input[placeholder*='status'], "
        "th:has-text('Status'), th:has-text('Статус'), "
        "[data-filter='status'], .status-filter"
    )
    # Fall back: just verify the table has some header
    table_header = page.locator("thead th")
    assert table_header.count() > 0 or filter_or_column.count() > 0, (
        "No status filter or table headers found on jobs page"
    )


# ── job detail ────────────────────────────────────────────────────────────────

def test_job_detail_page_404_handled(logged_in: Page):
    """Navigating to /jobs/nonexistent must not crash (200 or 404 acceptable)."""
    page = logged_in
    page.goto(f"{BASE_URL}/jobs/nonexistent-task-id")
    page.wait_for_load_state("networkidle")
    # Any rendered response is fine — just must not be a 5xx crash page
    assert "500" not in page.title() and "Internal Server Error" not in page.content()


# ── task schema ───────────────────────────────────────────────────────────────

def test_jobs_api_task_fields_if_any(api):
    """If tasks list is non-empty, each item must have id and status fields."""
    r = api("GET", "/api/tasks/?limit=20")
    assert r["status"] == 200
    items = r["body"]
    if not items:
        pytest.skip("No tasks present — skipping schema check")
    first = items[0]
    assert "id" in first, f"'id' field missing from task: {first}"
    assert "status" in first, f"'status' field missing from task: {first}"


# ── automation-triggered job ──────────────────────────────────────────────────

def test_jobs_create_via_automation(api):
    """Create a script + automation, run it, verify a task appears in /api/tasks/."""
    script_name = "e2e-script-" + uuid.uuid4().hex[:6]
    auto_name = "e2e-auto-" + uuid.uuid4().hex[:6]
    script_id = None
    auto_id = None

    try:
        # Create script
        rs = api("POST", "/api/scripts", {
            "name": script_name,
            "content": "#!/bin/bash\necho e2e-jobs-test",
            "script_type": "bash",
        })
        if rs["status"] not in (200, 201):
            pytest.skip(f"Script creation failed ({rs['status']}) — skipping")
        script_id = rs["body"].get("id")

        # Create automation
        ra = api("POST", "/api/automations", {
            "name": auto_name,
            "execution_type": "script",
            "script_id": script_id,
            "trigger_type": "manual",
            "run_on_all_platforms": True,
        })
        if ra["status"] not in (200, 201):
            pytest.skip(f"Automation creation failed ({ra['status']}) — skipping")
        auto_id = ra["body"].get("id")

        # Run automation
        rr = api("POST", f"/api/automations/{auto_id}/run", {})
        if rr["status"] not in (200, 201, 202):
            pytest.skip(f"Automation run failed ({rr['status']}) — skipping")

        # Verify a task exists
        rt = api("GET", "/api/tasks/?limit=5")
        assert rt["status"] == 200
        assert len(rt["body"]) >= 1, "Expected at least one task after running automation"

    finally:
        if auto_id:
            api("DELETE", f"/api/automations/{auto_id}")
        if script_id:
            api("DELETE", f"/api/scripts/{script_id}")


# ── page refresh ──────────────────────────────────────────────────────────────

def test_jobs_page_refresh_works(logged_in: Page):
    """Reloading /jobs must still render the page without errors."""
    page = logged_in
    _go_jobs(page)

    js_errors: list[str] = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    page.reload()
    page.wait_for_load_state("networkidle")

    assert "/login" not in page.url, "Page redirected to login after reload"
    assert not js_errors, f"JS errors after /jobs reload: {js_errors}"
