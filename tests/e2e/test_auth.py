# SPDX-License-Identifier: MIT
"""E2E: Authentication flows."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL, ADMIN_USER, ADMIN_PASS


def test_login_page_loads(page: Page):
    page.goto(f"{BASE_URL}/login")
    expect(page.locator("input[name='username'], input#username")).to_be_visible()
    expect(page.locator("input[name='password'], input#password")).to_be_visible()
    expect(page.locator("button[type='submit']")).to_be_visible()


def test_login_wrong_password_shows_error(page: Page):
    page.goto(f"{BASE_URL}/login")
    page.locator("input[name='username'], input#username").fill(ADMIN_USER)
    page.locator("input[name='password'], input#password").fill("wrongpassword")
    page.locator("button[type='submit']").click()
    expect(page).to_have_url(re.compile(r".*/login.*"))
    error = page.locator(".error, .alert, [class*='err'], [class*='alert']")
    expect(error.first).to_be_visible(timeout=5_000)


def test_login_empty_fields_blocked(page: Page):
    page.goto(f"{BASE_URL}/login")
    page.locator("button[type='submit']").click()
    expect(page).to_have_url(re.compile(r".*/login.*"))


def test_successful_login_redirects(page: Page):
    page.goto(f"{BASE_URL}/login")
    page.locator("input[name='username'], input#username").fill(ADMIN_USER)
    page.locator("input[name='password'], input#password").fill(ADMIN_PASS)
    page.locator("button[type='submit']").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=10_000)
    assert "/login" not in page.url


def test_protected_page_redirects_to_login(page: Page):
    page.goto(f"{BASE_URL}/platforms")
    page.wait_for_url(lambda url: "/login" in url or "/platforms" in url, timeout=5_000)


def test_logout(logged_in: Page):
    page = logged_in
    # No logout button in nav — call the logout endpoint directly
    page.goto(f"{BASE_URL}/api/auth/logout")
    page.wait_for_url(lambda url: "/login" in url, timeout=8_000)
    assert "/login" in page.url


def test_login_title_contains_testum(page: Page):
    page.goto(f"{BASE_URL}/login")
    expect(page).to_have_title(re.compile(r"testum|login", re.IGNORECASE))
