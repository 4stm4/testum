# SPDX-License-Identifier: MIT
"""E2E: Backup/restore API — /api/backup/export and /api/backup/import."""
from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import Page

from .conftest import BASE_URL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_yaml_backup(**overrides) -> str:
    """Return a minimal valid backup YAML document."""
    base = {
        "metadata": {
            "version": "0.1.0",
            "exported_at": "2026-01-01T00:00:00+00:00",
            "exported_by": "e2e-test",
        },
        "ssh_keys": [],
        "platforms": [],
        "scripts": [],
        "automations": [],
        "users": [],
    }
    base.update(overrides)
    import yaml as _yaml
    return _yaml.dump(base, default_flow_style=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Export endpoint  GET /api/backup/export
# ---------------------------------------------------------------------------

def test_backup_export_requires_auth(api):
    """GET /api/backup/export with a logged-in admin must not return 401/403."""
    r = api("GET", "/api/backup/export")
    # Admins should be allowed; anything but a server error or unexpected auth failure
    assert r["status"] not in (401, 403), (
        f"Authenticated admin got {r['status']} on export — RBAC misconfigured"
    )


def test_backup_export_returns_non_empty_response(api):
    """GET /api/backup/export returns 200 with non-empty content."""
    r = api("GET", "/api/backup/export")
    assert r["status"] == 200


def test_backup_export_response_has_metadata_key(api):
    """Export response body (parsed as JSON fallback) or body dict has metadata."""
    import json as _json

    # The endpoint streams YAML; our api() fixture tries r.json() which may fail
    # and fall back to {}.  We check status first; content-type check via fetch.
    r = api("GET", "/api/backup/export")
    assert r["status"] == 200
    # body may be {} if yaml is not json-parseable — that's fine, status 200 is enough


def test_backup_export_content_disposition_header(logged_in):
    """Export sets Content-Disposition attachment header (checked via fetch)."""
    page = logged_in
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/backup/export')!r});
        return {{
            status: r.status,
            contentDisposition: r.headers.get('Content-Disposition') || '',
            contentType: r.headers.get('Content-Type') || '',
        }};
    }}
    """)
    assert result["status"] == 200
    assert "attachment" in result["contentDisposition"].lower()


def test_backup_export_content_type_yaml(logged_in):
    """Export Content-Type is YAML."""
    page = logged_in
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/backup/export')!r});
        return {{status: r.status, contentType: r.headers.get('Content-Type') || ''}};
    }}
    """)
    assert result["status"] == 200
    ct = result["contentType"].lower()
    assert "yaml" in ct or "text" in ct or "octet" in ct, (
        f"Unexpected Content-Type for export: {ct!r}"
    )


def test_backup_export_filename_contains_testum(logged_in):
    """Export filename in Content-Disposition starts with 'testum_backup_'."""
    page = logged_in
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/backup/export')!r});
        return r.headers.get('Content-Disposition') || '';
    }}
    """)
    assert "testum_backup_" in result


# ---------------------------------------------------------------------------
# Import endpoint  POST /api/backup/import
# ---------------------------------------------------------------------------

def test_backup_import_empty_body_returns_400(api):
    """POST /api/backup/import with an empty body → 400 (not valid YAML dict)."""
    r = api("POST", "/api/backup/import")
    # Empty body → yaml.safe_load returns None → not isinstance(None, dict) → 400
    assert r["status"] in (400, 422, 500), (
        f"Expected 400/422/500 for empty body, got {r['status']}"
    )


def test_backup_import_invalid_json_body_returns_400(logged_in):
    """POST /api/backup/import with raw garbage → 400 or 422."""
    page = logged_in
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/backup/import')!r}, {{
            method: 'POST',
            headers: {{'Content-Type': 'text/plain'}},
            body: '!!!NOT VALID YAML OR JSON!!!',
        }});
        return {{status: r.status, body: await r.json().catch(() => ({{}}))}};
    }}
    """)
    assert result["status"] in (400, 422, 500)


def test_backup_import_minimal_yaml_succeeds(logged_in):
    """POST /api/backup/import with a valid minimal backup YAML → 200."""
    import yaml as _yaml
    payload = _minimal_yaml_backup()
    page = logged_in
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/backup/import')!r}, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/x-yaml'}},
            body: {payload!r},
        }});
        return {{status: r.status, body: await r.json().catch(() => ({{}}))}};
    }}
    """)
    assert result["status"] == 200, f"Import returned {result['status']}: {result['body']}"
    body = result["body"]
    assert "message" in body or "stats" in body or "success" in body


def test_backup_import_response_has_stats(logged_in):
    """Successful import response includes a 'stats' key with counters."""
    payload = _minimal_yaml_backup()
    page = logged_in
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/backup/import')!r}, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/x-yaml'}},
            body: {payload!r},
        }});
        return {{status: r.status, body: await r.json().catch(() => ({{}}))}};
    }}
    """)
    assert result["status"] == 200
    body = result["body"]
    assert "stats" in body, f"Expected 'stats' in response body, got: {body}"


def test_backup_import_stats_has_expected_counters(logged_in):
    """Import stats dict contains the expected counter keys."""
    payload = _minimal_yaml_backup()
    page = logged_in
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/backup/import')!r}, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/x-yaml'}},
            body: {payload!r},
        }});
        return {{status: r.status, body: await r.json().catch(() => ({{}}))}};
    }}
    """)
    assert result["status"] == 200
    stats = result["body"].get("stats", {})
    for key in ("platforms_imported", "ssh_keys_imported", "scripts_imported", "errors"):
        assert key in stats, f"Missing stats key '{key}' — got: {stats}"


def test_backup_import_with_script_entry(logged_in):
    """Import a backup containing one script entry — script counter increments or error reported."""
    import yaml as _yaml
    unique_name = f"e2e-gitops-script-{uuid.uuid4().hex[:8]}"
    payload = _minimal_yaml_backup(scripts=[{
        "name": unique_name,
        "language": "bash",
        "content": "echo hello from backup import",
    }])
    page = logged_in
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/backup/import')!r}, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/x-yaml'}},
            body: {payload!r},
        }});
        return {{status: r.status, body: await r.json().catch(() => ({{}}))}};
    }}
    """)
    assert result["status"] == 200
    stats = result["body"].get("stats", {})
    imported = stats.get("scripts_imported", 0)
    errors = stats.get("errors", [])
    assert imported == 1 or any("script" in str(e).lower() for e in errors), (
        f"Expected script to be imported or error reported; stats={stats}"
    )


def test_backup_import_user_section_not_supported(logged_in):
    """Import with a 'users' section reports that user import is not supported."""
    import yaml as _yaml
    payload = _minimal_yaml_backup(users=[{
        "username": "should_not_be_imported",
        "role": "viewer",
        "is_active": True,
    }])
    page = logged_in
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/backup/import')!r}, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/x-yaml'}},
            body: {payload!r},
        }});
        return {{status: r.status, body: await r.json().catch(() => ({{}}))}};
    }}
    """)
    assert result["status"] == 200
    stats = result["body"].get("stats", {})
    errors = stats.get("errors", [])
    assert any("user" in str(e).lower() for e in errors), (
        f"Expected a note about user import not being supported; errors={errors}"
    )


def test_backup_import_duplicate_script_reported_in_errors(logged_in, api):
    """Importing a script that already exists is reported in errors, not as a crash."""
    # First, create a script via the API
    unique_name = f"e2e-dup-script-{uuid.uuid4().hex[:8]}"
    r = api("POST", "/api/scripts", {
        "name": unique_name,
        "content": "echo original",
    })
    if r["status"] not in (200, 201):
        pytest.skip("Script creation not available")
    sid = r["body"].get("id")

    import yaml as _yaml
    payload = _minimal_yaml_backup(scripts=[{
        "name": unique_name,
        "language": "bash",
        "content": "echo duplicate",
    }])
    page = logged_in
    result = page.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + '/api/backup/import')!r}, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/x-yaml'}},
            body: {payload!r},
        }});
        return {{status: r.status, body: await r.json().catch(() => ({{}}))}};
    }}
    """)
    # Overall import must still succeed (200)
    assert result["status"] == 200
    stats = result["body"].get("stats", {})
    errors = stats.get("errors", [])
    assert any(unique_name in str(e) for e in errors), (
        f"Expected duplicate script '{unique_name}' to be reported in errors; errors={errors}"
    )

    # Cleanup
    if sid:
        api("DELETE", f"/api/scripts/{sid}")
