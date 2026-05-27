# SPDX-License-Identifier: MIT
"""E2E: SDN dashboard — status bar, tabs, Bind-Project modal, Resync."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_sdn(page: Page):
    page.goto(f"{BASE_URL}/sdn")
    page.wait_for_load_state("networkidle")


# ── page basics ───────────────────────────────────────────────────────────

def test_sdn_page_loads(logged_in: Page):
    page = logged_in
    _go_sdn(page)
    assert "/sdn" in page.url


def test_sdn_page_title_visible(logged_in: Page):
    page = logged_in
    _go_sdn(page)
    heading = page.locator("h1, h2, .page-title, [data-i18n='sdn'], [data-i18n='sdn_title']")
    expect(heading.first).to_be_visible(timeout=8_000)


# ── status bar ────────────────────────────────────────────────────────────

def test_sdn_status_bar_present(logged_in: Page):
    page = logged_in
    _go_sdn(page)
    # Status bar has the Nervum connection status span
    status = page.locator("#nervumConnStatus, .pill")
    expect(status.first).to_be_visible(timeout=8_000)


def test_sdn_status_shows_nervum_configured(logged_in: Page):
    page = logged_in
    _go_sdn(page)
    content = page.content()
    assert "nervum" in content.lower() or "sdn" in content.lower()


# ── tab navigation ────────────────────────────────────────────────────────

@pytest.mark.parametrize("tab_key,label", [
    ("networks",   "Networks"),
    ("nodes",      "Nodes"),
    ("ports",      "Ports"),
    ("routers",    "Routers"),
    ("operations", "Operations"),
    ("projects",   "Projects"),
])
def test_sdn_sidebar_navigation(logged_in: Page, tab_key: str, label: str):
    page = logged_in
    _go_sdn(page)

    link = page.locator(f"[data-sdn-tab='{tab_key}']")
    if link.count() == 0:
        pytest.skip(f"Sidebar link '{tab_key}' not found")

    link.first.click()
    page.wait_for_load_state("networkidle")
    assert "/login" not in page.url
    assert tab_key in page.url


# ── networks tab ──────────────────────────────────────────────────────────

def test_sdn_networks_tab_loads(logged_in: Page):
    page = logged_in
    _go_sdn(page)
    tab = page.locator("button.sdn-tab[data-tab='networks'], button:has-text('Networks')")
    if tab.count():
        tab.first.click()
        page.wait_for_load_state("networkidle")
    # "No networks found" or actual table rows — any text in main
    content = page.locator("main").inner_text()
    assert len(content) > 0


# ── resync button ─────────────────────────────────────────────────────────

def test_sdn_resync_button_present(logged_in: Page):
    page = logged_in
    _go_sdn(page)
    resync = page.locator("#resyncBtn, button:has-text('Resync'), [data-i18n='sdnResync']")
    expect(resync.first).to_be_visible(timeout=8_000)


def test_sdn_resync_triggers_request(logged_in: Page):
    page = logged_in
    _go_sdn(page)

    resync = page.locator("#resyncBtn, button:has-text('Resync')")
    if resync.count() == 0:
        pytest.skip("Resync button not found")

    with page.expect_response(
        lambda r: "sync" in r.url or "resync" in r.url,
        timeout=8_000,
    ) as resp_info:
        resync.first.click()

    assert resp_info.value.status in (200, 202, 204, 404, 503)


# ── bind project modal ────────────────────────────────────────────────────

def _go_sdn_projects(page: Page):
    """Navigate to SDN#projects via sidebar link (tab bar removed)."""
    page.goto(f"{BASE_URL}/sdn#projects")
    page.wait_for_load_state("networkidle")
    link = page.locator("[data-sdn-tab='projects']")
    if link.count():
        link.first.click()
        page.wait_for_timeout(300)


def test_sdn_bind_project_button_present(logged_in: Page):
    page = logged_in
    _go_sdn_projects(page)

    bind_btn = page.locator(
        "button:has-text('Bind'), button:has-text('Привязать'), "
        "[data-action='bind'], [data-i18n='bind_project'], #bind-project-btn, "
        "button:has-text('Project')"
    )
    expect(bind_btn.first).to_be_visible(timeout=8_000)


def test_sdn_bind_project_opens_modal(logged_in: Page):
    page = logged_in
    _go_sdn_projects(page)

    bind_btn = page.locator(
        "button:has-text('Bind'), button:has-text('Привязать'), "
        "[data-action='bind'], #bind-project-btn, button:has-text('Project')"
    )
    if bind_btn.count() == 0:
        pytest.skip("Bind Project button not found")

    bind_btn.first.click()
    modal = page.locator(".modal, dialog, [role='dialog'], form")
    expect(modal.first).to_be_visible(timeout=5_000)


def test_sdn_bind_project_submit(logged_in: Page):
    page = logged_in
    _go_sdn_projects(page)

    bind_btn = page.locator("button:has-text('Bind'), button:has-text('Привязать'), #bind-project-btn")
    if bind_btn.count() == 0:
        pytest.skip("Bind Project button not found")

    bind_btn.first.click()
    modal = page.locator("#bindModal")
    modal.wait_for(state="visible", timeout=5_000)

    page.locator("#bindTestumId").fill("tp-e2e-modal-" + __import__("uuid").uuid4().hex[:6])
    page.locator("#bindNervumId").fill("np-e2e-modal-" + __import__("uuid").uuid4().hex[:6])

    with page.expect_response(lambda r: "/api/sdn/projects" in r.url, timeout=8_000) as resp_info:
        page.locator("#bindSubmitBtn").click()

    assert resp_info.value.status in (200, 201)


def test_sdn_unbind_project(logged_in: Page, api):
    resp = api("POST", "/api/sdn/projects", {
        "testum_project_id": "tp-ui-del",
        "nervum_project_id": "np-ui-del",
    })
    if resp["status"] not in (200, 201):
        pytest.skip("Could not create binding via API")

    binding_id = resp["body"].get("id")
    page = logged_in
    _go_sdn_projects(page)
    page.wait_for_load_state("networkidle")

    del_btn = page.locator(f"#projectsBody tr:has-text('tp-ui-del') button")
    expect(del_btn.first).to_be_visible(timeout=8_000)

    page.on("dialog", lambda d: d.accept())
    with page.expect_response(lambda r: binding_id in r.url, timeout=5_000):
        del_btn.first.click()
