# SPDX-License-Identifier: MIT
"""E2E: Internationalisation — language switch EN ↔ RU."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import BASE_URL


def _click_lang(page: Page, lang: str):
    """Click the language toggle button (switches between EN and RU)."""
    btn = page.locator("#langToggle, .sb-lang-btn, [aria-label*='language'], [aria-label*='язык']")
    if btn.count() == 0:
        pytest.skip("Language toggle button not found")
    btn.first.click()
    page.wait_for_load_state("networkidle")


def test_language_switcher_present(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/")
    page.wait_for_load_state("networkidle")
    btn = page.locator("#langToggle, .sb-lang-btn")
    expect(btn.first).to_be_visible(timeout=8_000)


def test_switch_to_russian(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/")
    page.wait_for_load_state("networkidle")

    # The toggle button shows the OTHER language to switch to.
    # If button text is "RU" → currently EN, click to go RU.
    btn = page.locator("#langToggle, .sb-lang-btn")
    if btn.count() == 0:
        pytest.skip("Language toggle button not found")

    btn_text = btn.first.inner_text().strip()
    if btn_text.upper() == "EN":
        # Already in RU, just verify
        pass
    else:
        # Currently EN, click to switch to RU
        btn.first.click()
        page.wait_for_load_state("networkidle")

    # Check localStorage or aria-label for current lang
    lang = page.evaluate("() => localStorage.getItem('lang') || ''")
    # Language should be 'ru' or page contains Russian UI elements
    content = page.content()
    ru_words = ["Платформы", "Выход", "Пользователи", "Настройки", "Переключить", "Аудит"]
    has_ru = lang == "ru" or any(w in content for w in ru_words)
    assert has_ru, f"Expected RU language, lang={lang!r}, content snippet: {content[:500]}"


def test_switch_back_to_english(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/")
    page.wait_for_load_state("networkidle")

    btn = page.locator("#langToggle, .sb-lang-btn")
    if btn.count() == 0:
        pytest.skip("Language toggle button not found")

    btn_text = btn.first.inner_text().strip()
    if btn_text.upper() == "RU":
        # Currently EN, click once → RU, then again → EN
        btn.first.click()
        page.wait_for_load_state("networkidle")
        btn.first.click()
        page.wait_for_load_state("networkidle")
    # else: btn says EN → already in RU → click once
    else:
        btn.first.click()
        page.wait_for_load_state("networkidle")

    lang = page.evaluate("() => localStorage.getItem('lang') || ''")
    content = page.content()
    en_words = ["Platforms", "Users", "Scripts", "Audit", "Settings"]
    has_en = lang == "en" or any(w in content for w in en_words)
    assert has_en, f"Expected EN language, lang={lang!r}"


def test_language_persists_on_navigation(logged_in: Page):
    page = logged_in
    page.goto(f"{BASE_URL}/")
    page.wait_for_load_state("networkidle")

    btn = page.locator("#langToggle, .sb-lang-btn")
    if btn.count() == 0:
        pytest.skip("Language toggle button not found")

    btn.first.click()
    page.wait_for_load_state("networkidle")

    lang_after_click = page.evaluate("() => localStorage.getItem('lang') || ''")

    page.goto(f"{BASE_URL}/platforms")
    page.wait_for_load_state("networkidle")

    lang_after_nav = page.evaluate("() => localStorage.getItem('lang') || ''")
    assert lang_after_nav == lang_after_click, (
        f"Language changed on navigation: {lang_after_click!r} → {lang_after_nav!r}"
    )
    assert "/login" not in page.url
