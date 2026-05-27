# SPDX-License-Identifier: MIT
"""Integration tests for SDN API endpoints."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest
from starlette.testclient import TestClient


# ── Helpers ───────────────────────────────────────────────────────────────

def _seed_nervum_data(db):
    """Populate replica tables with test data."""
    from datetime import datetime
    from adapters.postgres.orm_models import (
        NervumNetworkRow, NervumNodeRow, NervumLogicalPortRow,
        NervumRouterRow, SdnTaskRow,
    )

    db.add(NervumNetworkRow(
        id="net-1", name="prod-net", type="vxlan", project_id="proj-1",
        vni=100, vlan_id=None, mtu=1500, updated_at=datetime.utcnow(),
    ))
    db.add(NervumNetworkRow(
        id="net-2", name="mgmt-net", type="flat", project_id="proj-2",
        updated_at=datetime.utcnow(),
    ))
    db.add(NervumNodeRow(
        id="node-1", name="worker-01", mgmt_ip="10.0.0.1",
        status="active", agent_version="0.1.0", updated_at=datetime.utcnow(),
    ))
    db.add(NervumLogicalPortRow(
        id="port-1", name="vm-web", network_id="net-1", project_id="proj-1",
        status="active", mac="02:aa:bb:cc:dd:01", ip_address="10.0.1.5",
        updated_at=datetime.utcnow(),
    ))
    db.add(NervumRouterRow(
        id="router-1", name="edge-gw", project_id="proj-1",
        status="active", mode="off", updated_at=datetime.utcnow(),
    ))
    db.add(SdnTaskRow(
        id=uuid.uuid4(), nervum_operation_id="op-abc", project_id="proj-1",
        kind="network.create", status="succeeded",
        started_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    ))
    db.commit()


# ── sync/status ───────────────────────────────────────────────────────────

def test_sync_status_returns_all_counts(client: TestClient, test_db):
    _seed_nervum_data(test_db)
    r = client.get("/api/sdn/sync/status")
    assert r.status_code == 200
    data = r.json()
    assert "watermark" in data
    assert "network_count" in data
    assert "logical_port_count" in data
    assert "router_count" in data
    assert "vpn_tunnel_count" in data
    assert data["network_count"] == 2
    assert data["node_count"] == 1
    assert data["logical_port_count"] == 1


def test_sync_status_nervum_not_configured(client: TestClient, test_db):
    r = client.get("/api/sdn/sync/status")
    assert r.status_code == 200
    assert r.json()["nervum_configured"] is False


# ── networks ──────────────────────────────────────────────────────────────

def test_list_networks_empty(client: TestClient, test_db):
    r = client.get("/api/sdn/networks")
    assert r.status_code == 200
    assert r.json() == []


def test_list_networks(client: TestClient, test_db):
    _seed_nervum_data(test_db)
    r = client.get("/api/sdn/networks")
    assert r.status_code == 200
    nets = r.json()
    assert len(nets) == 2
    names = {n["name"] for n in nets}
    assert "prod-net" in names


def test_list_networks_filter_by_project(client: TestClient, test_db):
    _seed_nervum_data(test_db)
    r = client.get("/api/sdn/networks?project_id=proj-1")
    assert r.status_code == 200
    nets = r.json()
    assert len(nets) == 1
    assert nets[0]["project_id"] == "proj-1"


# ── nodes ─────────────────────────────────────────────────────────────────

def test_list_nodes(client: TestClient, test_db):
    _seed_nervum_data(test_db)
    r = client.get("/api/sdn/nodes")
    assert r.status_code == 200
    nodes = r.json()
    assert len(nodes) == 1
    assert nodes[0]["name"] == "worker-01"
    assert nodes[0]["status"] == "active"


# ── logical ports ─────────────────────────────────────────────────────────

def test_list_logical_ports(client: TestClient, test_db):
    _seed_nervum_data(test_db)
    r = client.get("/api/sdn/logical-ports")
    assert r.status_code == 200
    ports = r.json()
    assert len(ports) == 1
    assert ports[0]["mac"] == "02:aa:bb:cc:dd:01"


def test_list_logical_ports_filter_network(client: TestClient, test_db):
    _seed_nervum_data(test_db)
    r = client.get("/api/sdn/logical-ports?network_id=net-1")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r2 = client.get("/api/sdn/logical-ports?network_id=net-999")
    assert r2.status_code == 200
    assert r2.json() == []


def test_get_logical_port(client: TestClient, test_db):
    _seed_nervum_data(test_db)
    r = client.get("/api/sdn/logical-ports/port-1")
    assert r.status_code == 200
    assert r.json()["ip_address"] == "10.0.1.5"


def test_get_logical_port_not_found(client: TestClient, test_db):
    r = client.get("/api/sdn/logical-ports/port-does-not-exist")
    assert r.status_code == 404


# ── routers ───────────────────────────────────────────────────────────────

def test_list_routers(client: TestClient, test_db):
    _seed_nervum_data(test_db)
    r = client.get("/api/sdn/routers")
    assert r.status_code == 200
    routers = r.json()
    assert len(routers) == 1
    assert routers[0]["status"] == "active"


def test_list_routers_filter_project(client: TestClient, test_db):
    _seed_nervum_data(test_db)
    r = client.get("/api/sdn/routers?project_id=proj-999")
    assert r.status_code == 200
    assert r.json() == []


# ── operations ────────────────────────────────────────────────────────────

def test_list_operations(client: TestClient, test_db):
    _seed_nervum_data(test_db)
    r = client.get("/api/sdn/operations")
    assert r.status_code == 200
    ops = r.json()
    assert len(ops) == 1
    assert ops[0]["status"] == "succeeded"


def test_list_operations_filter_status(client: TestClient, test_db):
    _seed_nervum_data(test_db)
    r = client.get("/api/sdn/operations?status=failed")
    assert r.status_code == 200
    assert r.json() == []


def test_list_operations_limit(client: TestClient, test_db):
    from datetime import datetime
    from adapters.postgres.orm_models import SdnTaskRow
    for i in range(10):
        test_db.add(SdnTaskRow(
            id=uuid.uuid4(), nervum_operation_id=f"op-{i}",
            status="succeeded", started_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        ))
    test_db.commit()

    r = client.get("/api/sdn/operations?limit=5")
    assert r.status_code == 200
    assert len(r.json()) <= 5


def test_get_operation_not_found(client: TestClient, test_db):
    r = client.get(f"/api/sdn/operations/{uuid.uuid4()}")
    assert r.status_code == 404


# ── webhook receiver ──────────────────────────────────────────────────────

def test_webhook_no_secret_accepts(client: TestClient, test_db):
    """Без NERVUM_WEBHOOK_SECRET любой запрос принимается."""
    ev = {
        "schema_version": 2, "event_id": 99,
        "event_type": "network.created", "resource_type": "network",
        "resource_id": "net-hook", "project_id": "p1",
        "payload": {"name": "hook-net"},
    }
    r = client.post("/webhooks/nervum", json=ev)
    assert r.status_code == 202
    assert r.json()["status"] == "accepted"


def test_webhook_valid_hmac(client: TestClient, test_db):
    secret = "testsecret"
    body = json.dumps({"schema_version": 2, "event_id": 101, "event_type": "node.registered",
                       "resource_type": "node", "resource_id": "node-w",
                       "payload": {"name": "w1"}}).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    import os
    old = os.environ.get("NERVUM_WEBHOOK_SECRET")
    os.environ["NERVUM_WEBHOOK_SECRET"] = secret
    try:
        # reload config value
        from app.config import Config
        Config.NERVUM_WEBHOOK_SECRET = secret
        r = client.post(
            "/webhooks/nervum",
            content=body,
            headers={"Content-Type": "application/json", "X-SDN-Signature": sig},
        )
        assert r.status_code == 202
    finally:
        if old is None:
            del os.environ["NERVUM_WEBHOOK_SECRET"]
        else:
            os.environ["NERVUM_WEBHOOK_SECRET"] = old
        Config.NERVUM_WEBHOOK_SECRET = old


def test_webhook_invalid_hmac_rejected(client: TestClient, test_db):
    import os
    old = os.environ.get("NERVUM_WEBHOOK_SECRET")
    os.environ["NERVUM_WEBHOOK_SECRET"] = "realsecret"
    from app.config import Config
    Config.NERVUM_WEBHOOK_SECRET = "realsecret"
    try:
        r = client.post(
            "/webhooks/nervum",
            json={"schema_version": 2, "event_id": 1, "event_type": "x",
                  "resource_type": "network", "resource_id": "n"},
            headers={"X-SDN-Signature": "sha256=deadbeef"},
        )
        assert r.status_code == 401
    finally:
        if old is None and "NERVUM_WEBHOOK_SECRET" in os.environ:
            del os.environ["NERVUM_WEBHOOK_SECRET"]
        else:
            os.environ["NERVUM_WEBHOOK_SECRET"] = old or ""
        Config.NERVUM_WEBHOOK_SECRET = old


def test_webhook_duplicate_delivery_id(client: TestClient, test_db):
    from ports.api.nervum import _seen_delivery_ids
    _seen_delivery_ids.clear()

    ev = {"schema_version": 2, "event_id": 200, "event_type": "network.created",
          "resource_type": "network", "resource_id": "net-dup", "payload": {"name": "dup"}}

    r1 = client.post("/webhooks/nervum", json=ev,
                     headers={"X-SDN-Delivery-Id": "delivery-abc"})
    assert r1.status_code == 202

    r2 = client.post("/webhooks/nervum", json=ev,
                     headers={"X-SDN-Delivery-Id": "delivery-abc"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"


def test_webhook_invalid_json(client: TestClient, test_db):
    r = client.post(
        "/webhooks/nervum",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400


# ── project bindings ──────────────────────────────────────────────────────

def test_project_binding_crud(client: TestClient, test_db):
    payload = {
        "testum_project_id": "tp-001",
        "nervum_project_id": "np-001",
        "nervum_project_slug": "my-project",
    }
    # Starlette Mount strips prefix — try both with and without trailing slash
    r = client.post("/api/sdn/projects/", json=payload)
    if r.status_code == 404:
        r = client.post("/api/sdn/projects", json=payload)
    assert r.status_code in (200, 201)
    data = r.json()
    assert data["testum_project_id"] == "tp-001"
    binding_id = data["id"]

    # список
    r2 = client.get("/api/sdn/projects/")
    if r2.status_code == 404:
        r2 = client.get("/api/sdn/projects")
    assert r2.status_code == 200
    assert any(b["id"] == binding_id for b in r2.json())

    # удаление
    r3 = client.delete(f"/api/sdn/projects/{binding_id}")
    assert r3.status_code == 200

    r4 = client.get("/api/sdn/projects/")
    assert not any(b["id"] == binding_id for b in r4.json())


def test_project_binding_idempotent(client: TestClient, test_db):
    payload = {"testum_project_id": "tp-idem", "nervum_project_id": "np-idem"}

    def _post_binding(p):
        r = client.post("/api/sdn/projects/", json=p)
        return r if r.status_code != 404 else client.post("/api/sdn/projects", json=p)

    r1 = _post_binding(payload)
    r2 = _post_binding(payload)
    assert r1.status_code in (200, 201)
    assert r2.status_code in (200, 201)

    r = client.get("/api/sdn/projects/")
    if r.status_code == 404:
        r = client.get("/api/sdn/projects")
    bindings = [b for b in r.json() if b["testum_project_id"] == "tp-idem"]
    assert len(bindings) == 1


def test_project_binding_delete_not_found(client: TestClient, test_db):
    r = client.delete(f"/api/sdn/projects/{uuid.uuid4()}")
    assert r.status_code == 404
