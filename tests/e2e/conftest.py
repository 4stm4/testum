# SPDX-License-Identifier: MIT
"""E2E test configuration for Playwright."""
from __future__ import annotations

import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.getenv("TESTUM_URL", "http://localhost:8080")
ADMIN_USER = os.getenv("TESTUM_ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("TESTUM_ADMIN_PASS", "admin123")


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: end-to-end browser tests")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture()
def logged_in(page: Page) -> Page:
    """Navigate to app and log in as admin, return authenticated page."""
    page.goto(f"{BASE_URL}/login")
    page.locator("input#username, input[name='username']").fill(ADMIN_USER)
    page.locator("input#password, input[name='password']").fill(ADMIN_PASS)
    page.locator("button[type='submit']").click()
    # Wait until redirected away from /login
    page.wait_for_url(lambda url: "/login" not in url, timeout=15_000)
    return page


@pytest.fixture()
def api(logged_in: Page):
    """Helper: make authenticated API calls via fetch() in the browser context."""
    import json as _json

    def _fetch(method: str, path: str, body: dict | None = None) -> dict:
        body_js = f"opts.body = JSON.stringify({_json.dumps(body)});" if body else ""
        script = f"""
        async () => {{
            const opts = {{method: {method!r}, headers: {{'Content-Type': 'application/json'}}}};
            {body_js}
            const r = await fetch({(BASE_URL + path)!r}, opts);
            return {{status: r.status, body: await r.json().catch(() => ({{}})) }};
        }}
        """
        return logged_in.evaluate(script)
    return _fetch
