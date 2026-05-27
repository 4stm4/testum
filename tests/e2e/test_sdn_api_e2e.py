# SPDX-License-Identifier: MIT
"""E2E: All SDN API endpoints — exercised via authenticated browser fetch()."""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from playwright.sync_api import Page

from .conftest import BASE_URL


# ── sync/status ───────────────────────────────────────────────────────────

def test_api_sdn_sync_status(api):
    r = api("GET", "/api/sdn/sync/status")
    assert r["status"] == 200
    body = r["body"]
    assert "nervum_configured" in body


def test_api_sdn_sync_status_has_counts(api):
    r = api("GET", "/api/sdn/sync/status")
    body = r["body"]
    for key in ("network_count", "node_count", "logical_port_count", "router_count"):
        assert key in body, f"Missing key: {key}"


# ── trigger resync ────────────────────────────────────────────────────────

def test_api_sdn_trigger_resync(api):
    r = api("POST", "/api/sdn/sync/trigger")
    assert r["status"] in (200, 202, 404, 503)   # 503 when NERVUM_URL not configured


# ── networks ──────────────────────────────────────────────────────────────

def test_api_sdn_list_networks_empty(api):
    r = api("GET", "/api/sdn/networks")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_sdn_list_networks_filter_project(api):
    r = api("GET", "/api/sdn/networks?project_id=proj-nonexistent")
    assert r["status"] == 200
    assert r["body"] == []


# ── nodes ─────────────────────────────────────────────────────────────────

def test_api_sdn_list_nodes(api):
    r = api("GET", "/api/sdn/nodes")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


# ── logical ports ─────────────────────────────────────────────────────────

def test_api_sdn_list_logical_ports(api):
    r = api("GET", "/api/sdn/logical-ports")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_sdn_logical_port_filter_network(api):
    r = api("GET", "/api/sdn/logical-ports?network_id=net-no-exist")
    assert r["status"] == 200
    assert r["body"] == []


def test_api_sdn_get_logical_port_not_found(api):
    r = api("GET", "/api/sdn/logical-ports/port-does-not-exist")
    assert r["status"] == 404


# ── routers ───────────────────────────────────────────────────────────────

def test_api_sdn_list_routers(api):
    r = api("GET", "/api/sdn/routers")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_sdn_list_routers_filter_project(api):
    r = api("GET", "/api/sdn/routers?project_id=proj-none")
    assert r["status"] == 200
    assert r["body"] == []


# ── operations ────────────────────────────────────────────────────────────

def test_api_sdn_list_operations(api):
    r = api("GET", "/api/sdn/operations")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_sdn_list_operations_filter_status(api):
    r = api("GET", "/api/sdn/operations?status=failed")
    assert r["status"] == 200
    assert isinstance(r["body"], list)


def test_api_sdn_list_operations_limit(api):
    r = api("GET", "/api/sdn/operations?limit=3")
    assert r["status"] == 200
    assert len(r["body"]) <= 3


def test_api_sdn_get_operation_not_found(api):
    import uuid
    r = api("GET", f"/api/sdn/operations/{uuid.uuid4()}")
    assert r["status"] == 404


# ── project bindings ──────────────────────────────────────────────────────

def test_api_sdn_project_binding_lifecycle(api):
    """Create → List → Delete a project binding."""
    # Create
    r = api("POST", "/api/sdn/projects/", {
        "testum_project_id": "tp-e2e-api",
        "nervum_project_id": "np-e2e-api",
        "nervum_project_slug": "e2e-api",
    })
    assert r["status"] in (200, 201), f"Create failed: {r}"
    binding_id = r["body"]["id"]

    # List — should include our binding
    r2 = api("GET", "/api/sdn/projects/")
    assert r2["status"] == 200
    ids = [b["id"] for b in r2["body"]]
    assert binding_id in ids

    # Delete
    r3 = api("DELETE", f"/api/sdn/projects/{binding_id}/")
    assert r3["status"] == 200

    # Verify removed
    r4 = api("GET", "/api/sdn/projects/")
    ids_after = [b["id"] for b in r4["body"]]
    assert binding_id not in ids_after


def test_api_sdn_project_binding_idempotent(api):
    payload = {"testum_project_id": "tp-idem-e2e", "nervum_project_id": "np-idem-e2e"}
    r1 = api("POST", "/api/sdn/projects/", payload)
    r2 = api("POST", "/api/sdn/projects/", payload)
    assert r1["status"] in (200, 201)
    assert r2["status"] in (200, 201)

    r = api("GET", "/api/sdn/projects/")
    bindings = [b for b in r["body"] if b["testum_project_id"] == "tp-idem-e2e"]
    assert len(bindings) == 1

    # Cleanup
    api("DELETE", f"/api/sdn/projects/{bindings[0]['id']}/")


def test_api_sdn_project_binding_delete_not_found(api):
    import uuid
    r = api("DELETE", f"/api/sdn/projects/{uuid.uuid4()}/")
    assert r["status"] == 404


# ── webhook ───────────────────────────────────────────────────────────────

def test_api_sdn_webhook_accepts_no_secret(logged_in: Page):
    """POST /webhooks/nervum without HMAC — should accept (202) when no secret configured."""
    ev = json.dumps({
        "schema_version": 2, "event_id": 9001,
        "event_type": "network.created", "resource_type": "network",
        "resource_id": "net-e2e-wh", "project_id": "p1",
        "payload": {"name": "e2e-wh-net"},
    })
    result = logged_in.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + "/webhooks/nervum")!r}, {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: {ev!r},
        }});
        return r.status;
    }}
    """)
    assert result in (200, 202)


def test_api_sdn_webhook_invalid_json(logged_in: Page):
    result = logged_in.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + "/webhooks/nervum")!r}, {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: "not-json",
        }});
        return r.status;
    }}
    """)
    assert result == 400


def test_api_sdn_webhook_duplicate_delivery(logged_in: Page):
    ev = json.dumps({
        "schema_version": 2, "event_id": 9002,
        "event_type": "network.created", "resource_type": "network",
        "resource_id": "net-dup-e2e", "payload": {"name": "dup"},
    })
    delivery_id = "e2e-delivery-dup-001"

    status1 = logged_in.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + "/webhooks/nervum")!r}, {{
            method: "POST",
            headers: {{"Content-Type": "application/json", "X-SDN-Delivery-Id": {delivery_id!r}}},
            body: {ev!r},
        }});
        return r.status;
    }}
    """)

    status2 = logged_in.evaluate(f"""
    async () => {{
        const r = await fetch({(BASE_URL + "/webhooks/nervum")!r}, {{
            method: "POST",
            headers: {{"Content-Type": "application/json", "X-SDN-Delivery-Id": {delivery_id!r}}},
            body: {ev!r},
        }});
        return r.status;
    }}
    """)

    assert status1 in (200, 202)
    assert status2 == 200  # duplicate → 200 with status=duplicate
