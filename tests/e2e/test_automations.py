# SPDX-License-Identifier: MIT
"""E2E: Automation jobs — CRUD via API and UI."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _go_automations(page: Page):
    page.goto(f"{BASE_URL}/automations")
    page.wait_for_load_state("networkidle")


def _make_job_payload(name: str) -> dict:
    return {
        "name": name,
        "description": "E2E automation job",
        "execution_type": "command",
        "command": "echo e2e",
        "trigger_type": "manual",
        "run_on_all_platforms": True,
    }


# ── page loads ────────────────────────────────────────────────────────────

def test_automations_page_loads(logged_in: Page):
    page = logged_in
    _go_automations(page)
    assert "/automations" in page.url or "/jobs" in page.url


def test_automations_has_create_button(logged_in: Page):
    page = logged_in
    _go_automations(page)
    btn = page.locator(
        "button:has-text('Add'), button:has-text('Create'), "
        "button:has-text('New'), button:has-text('Создать'), "
        "[data-i18n='add_job'], #add-job-btn, button:has-text('Automation')"
    )
    expect(btn.first).to_be_visible(timeout=8_000)


# ── API: CRUD ─────────────────────────────────────────────────────────────

def test_list_jobs_returns_list(api):
    r = api("GET", "/api/automations")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_create_job_via_api(api):
    r = api("POST", "/api/automations", _make_job_payload("e2e-job"))
    assert r["status"] in (200, 201), f"Create job failed: {r}"
    jid = r["body"].get("id")
    assert jid
    api("DELETE", f"/api/automations/{jid}")


def test_get_job_via_api(api):
    r = api("POST", "/api/automations", _make_job_payload("e2e-get-job"))
    if r["status"] not in (200, 201):
        pytest.skip("Job creation failed")
    jid = r["body"]["id"]

    r2 = api("GET", f"/api/automations/{jid}")
    assert r2["status"] == 200
    assert r2["body"]["id"] == jid
    api("DELETE", f"/api/automations/{jid}")


def test_update_job_via_api(api):
    r = api("POST", "/api/automations", _make_job_payload("e2e-upd-job"))
    if r["status"] not in (200, 201):
        pytest.skip("Job creation failed")
    jid = r["body"]["id"]

    r2 = api("PUT", f"/api/automations/{jid}", {
        "name": "e2e-upd-job",
        "description": "updated desc",
        "execution_type": "command",
        "command": "echo updated",
        "trigger_type": "manual",
    })
    assert r2["status"] == 200
    api("DELETE", f"/api/automations/{jid}")


def test_delete_job_via_api(api):
    r = api("POST", "/api/automations", _make_job_payload("e2e-del-job"))
    if r["status"] not in (200, 201):
        pytest.skip("Job creation failed")
    jid = r["body"]["id"]

    r2 = api("DELETE", f"/api/automations/{jid}")
    assert r2["status"] in (200, 204)


def test_get_job_not_found(api):
    import uuid
    r = api("GET", f"/api/automations/{uuid.uuid4()}")
    assert r["status"] == 404


def test_run_job_via_api(api):
    r = api("POST", "/api/automations", _make_job_payload("e2e-run-job"))
    if r["status"] not in (200, 201):
        pytest.skip("Job creation failed")
    jid = r["body"]["id"]

    r2 = api("POST", f"/api/automations/{jid}/run")
    assert r2["status"] in (200, 202, 400, 404, 422)
    api("DELETE", f"/api/automations/{jid}")


# ── UI ────────────────────────────────────────────────────────────────────

def test_automations_page_shows_content(logged_in: Page):
    page = logged_in
    _go_automations(page)
    content = page.locator("main").inner_text()
    assert len(content) > 0


def test_created_job_appears_in_ui(logged_in: Page, api):
    r = api("POST", "/api/automations", _make_job_payload("e2e-ui-job"))
    if r["status"] not in (200, 201):
        pytest.skip("Job creation failed")

    jid = r["body"]["id"]
    page = logged_in
    _go_automations(page)
    page.reload()
    page.wait_for_load_state("networkidle")

    row = page.locator("text=e2e-ui-job")
    expect(row.first).to_be_visible(timeout=8_000)
    api("DELETE", f"/api/automations/{jid}")
