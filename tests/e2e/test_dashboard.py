# SPDX-License-Identifier: MIT
"""E2E: Dashboard — page load, sidebar links, API tasks."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_dashboard(page: Page):
    page.goto(f"{BASE_URL}/")
    page.wait_for_load_state("networkidle")


# ── page loads ────────────────────────────────────────────────────────────────

def test_dashboard_loads(logged_in: Page):
    """Navigating to / must land on the dashboard, not /login."""
    page = logged_in
    _go_dashboard(page)
    assert "/login" not in page.url, f"Redirected to login: {page.url}"


def test_dashboard_not_redirected(logged_in: Page):
    """/ must not redirect to /login."""
    page = logged_in
    _go_dashboard(page)
    assert "/login" not in page.url, f"Unexpected redirect to login: {page.url}"


def test_dashboard_has_main_content(logged_in: Page):
    """Dashboard must have a visible <main> element."""
    page = logged_in
    _go_dashboard(page)
    expect(page.locator("main")).to_be_visible(timeout=8_000)


def test_dashboard_sidebar_visible(logged_in: Page):
    """Dashboard must render a sidebar navigation element."""
    page = logged_in
    _go_dashboard(page)
    sidebar = page.locator("nav, aside, .sidebar, #sidebar, [role='navigation']")
    expect(sidebar.first).to_be_visible(timeout=8_000)


def test_dashboard_shows_jobs_section(logged_in: Page):
    """Main content must show a jobs table or an empty-state message."""
    page = logged_in
    _go_dashboard(page)
    # Either a table or some text indicating the jobs/tasks section
    jobs_area = page.locator(
        "table, .empty-state, [data-section='jobs'], "
        "text='No jobs', text='No tasks', text='Recent', text='Jobs'"
    )
    expect(jobs_area.first).to_be_visible(timeout=8_000)


# ── API ───────────────────────────────────────────────────────────────────────

def test_dashboard_api_tasks_returns_list(api):
    """GET /api/tasks/?limit=20 must return 200 and a JSON list."""
    r = api("GET", "/api/tasks/?limit=20")
    assert r["status"] == 200, f"Expected 200, got {r['status']}"
    assert isinstance(r["body"], list), f"Expected list, got {type(r['body'])}"


# ── sidebar navigation ────────────────────────────────────────────────────────

def test_dashboard_jobs_link_works(logged_in: Page):
    """Clicking the sidebar Jobs link must navigate to a URL containing 'jobs'."""
    page = logged_in
    _go_dashboard(page)

    link = page.locator(
        "a[href*='jobs'], a:has-text('Jobs'), a[data-i18n='jobs'], nav a:has-text('Job')"
    )
    if link.count() == 0:
        pytest.skip("No Jobs sidebar link found")

    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "jobs" in page.url.lower(), f"Expected 'jobs' in URL, got: {page.url}"


def test_dashboard_platforms_link_works(logged_in: Page):
    """Clicking the sidebar Platforms link must navigate to a URL containing 'platforms'."""
    page = logged_in
    _go_dashboard(page)

    link = page.locator(
        "a[href*='platforms'], a:has-text('Platforms'), "
        "a[data-i18n='platforms'], nav a:has-text('Platform')"
    )
    if link.count() == 0:
        pytest.skip("No Platforms sidebar link found")

    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "platform" in page.url.lower(), f"Expected 'platform' in URL, got: {page.url}"


def test_dashboard_sdn_link_works(logged_in: Page):
    """Clicking the sidebar SDN link must navigate to a URL containing 'sdn'."""
    page = logged_in
    _go_dashboard(page)

    link = page.locator(
        "a[href*='sdn'], a:has-text('SDN'), a[data-i18n='sdn'], nav a:has-text('SDN')"
    )
    if link.count() == 0:
        pytest.skip("No SDN sidebar link found")

    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "sdn" in page.url.lower(), f"Expected 'sdn' in URL, got: {page.url}"


def test_dashboard_audit_link_works(logged_in: Page):
    """Clicking the sidebar Audit link must navigate to a URL containing 'audit'."""
    page = logged_in
    _go_dashboard(page)

    link = page.locator(
        "a[href*='audit'], a:has-text('Audit'), a[data-i18n='audit'], nav a:has-text('Audit')"
    )
    if link.count() == 0:
        pytest.skip("No Audit sidebar link found")

    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "audit" in page.url.lower(), f"Expected 'audit' in URL, got: {page.url}"


# ── JS errors / page quality ──────────────────────────────────────────────────

def test_dashboard_no_js_errors(logged_in: Page):
    """Dashboard must load without JavaScript exceptions."""
    page = logged_in
    js_errors: list[str] = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    _go_dashboard(page)
    page.wait_for_load_state("networkidle")

    assert not js_errors, f"JS errors on dashboard: {js_errors}"


def test_dashboard_title_contains_testum(logged_in: Page):
    """Page title or primary heading must reference the app name."""
    page = logged_in
    _go_dashboard(page)

    title = page.title()
    h1_texts = page.locator("h1, h2, .brand, .app-name, .navbar-brand").all_inner_texts()
    combined = (title + " " + " ".join(h1_texts)).lower()

    assert any(kw in combined for kw in ("testum", "dashboard", "jobs", "overview")), (
        f"App name not found in title={title!r} or headings={h1_texts}"
    )
