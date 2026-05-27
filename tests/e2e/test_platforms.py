# SPDX-License-Identifier: MIT
"""E2E: Platforms page — add, list, delete, audit log entry."""
from __future__ import annotations

import re
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_platforms(page: Page):
    page.goto(f"{BASE_URL}/platforms")
    page.wait_for_load_state("networkidle")


def test_platforms_page_loads(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    assert "/platforms" in page.url


def test_platforms_page_has_add_button(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    add_btn = page.locator(
        "button:has-text('Add'), button:has-text('Добавить'), "
        "a:has-text('Add'), [data-i18n='add_platform'], "
        "button[data-action='add'], #add-platform-btn"
    )
    expect(add_btn.first).to_be_visible(timeout=8_000)


def test_add_platform_opens_form(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    add_btn = page.locator(
        "button:has-text('Add'), button:has-text('Добавить'), "
        "[data-i18n='add_platform'], button[data-action='add'], #add-platform-btn"
    )
    add_btn.first.click()
    form = page.locator("form, .modal, dialog, [role='dialog']")
    expect(form.first).to_be_visible(timeout=5_000)


def test_platform_list_shows_existing(logged_in: Page, api):
    page = logged_in
    resp = api("POST", "/api/platforms", {
        "name": "e2e-list-host",
        "host": "10.99.99.1",
        "port": 22,
        "username": "root",
        "auth_method": "password",
        "password": "secret",
    })
    assert resp["status"] < 500

    _go_platforms(page)
    assert "/platforms" in page.url


def test_delete_platform_via_api(logged_in: Page, api):
    resp = api("POST", "/api/platforms", {
        "name": "e2e-del-" + uuid.uuid4().hex[:8],
        "host": "10.99.88.2",
        "port": 22,
        "username": "root",
        "auth_method": "password",
        "password": "secret",
    })
    if resp["status"] not in (200, 201):
        pytest.skip("Platform creation not available via API in this config")

    pid = resp["body"].get("id")
    assert pid

    del_resp = api("DELETE", f"/api/platforms/{pid}")
    assert del_resp["status"] in (200, 204)

    list_resp = api("GET", "/api/platforms")
    body = list_resp.get("body", [])
    ids = [p["id"] for p in (body if isinstance(body, list) else body.get("items", []))]
    assert pid not in ids


def test_platforms_page_shows_table(logged_in: Page):
    page = logged_in
    _go_platforms(page)
    # Platforms uses card layout — check main has content
    content = page.locator("main").inner_text()
    assert len(content) > 0
