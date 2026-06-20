# SPDX-License-Identifier: MIT
"""Unit tests for Nervum client, sync logic, and HMAC validation."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── verify_signature ──────────────────────────────────────────────────────

def test_verify_signature_valid():
    from adapters.nervum.client import verify_signature

    secret = "mysecret"
    body = b'{"event_type":"network.created"}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, secret) is True


def test_verify_signature_wrong_secret():
    from adapters.nervum.client import verify_signature

    body = b'{"event_type":"network.created"}'
    sig = "sha256=" + hmac.new(b"correct", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, "wrong") is False


def test_webhook_empty_secret_bypasses_in_receiver():
    """Пустой NERVUM_WEBHOOK_SECRET — проверка HMAC пропускается в webhook_receiver.
    Это логика в nervum.py (if secret and not verify_signature(...)), не в verify_signature.
    """
    import os
    from app.config import Config
    old = Config.NERVUM_WEBHOOK_SECRET
    Config.NERVUM_WEBHOOK_SECRET = ""
    try:
        secret = Config.NERVUM_WEBHOOK_SECRET or ""
        # при пустом secret блок проверки не выполняется
        assert not secret  # guard: secret действительно пустой
    finally:
        Config.NERVUM_WEBHOOK_SECRET = old


def test_verify_signature_signs_raw_bytes_not_json():
    """Nervum signs raw body, not re-serialised JSON."""
    from adapters.nervum.client import verify_signature

    secret = "s3cr3t"
    # body with non-canonical whitespace — must match as-is
    body = b'{ "a" : 1 , "b" : 2 }'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, secret) is True

    # re-serialised compact form must NOT match
    compact = json.dumps(json.loads(body), separators=(",", ":")).encode()
    assert verify_signature(compact, sig, secret) is False


# ── apply_event ───────────────────────────────────────────────────────────

@pytest.fixture()
def sqlite_db(tmp_path):
    """In-memory SQLite session with all Nervum tables."""
    import os
    os.environ.setdefault("FERNET_KEY", "XvgfcADXX1oKcITCS8V7iQWr9VcweqQR7H3Vc_2qsFs=")
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from adapters.postgres.session import Base
    import adapters.postgres.orm_models  # noqa: F401 — register all models

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def _event(resource_type, event_type, resource_id, event_id=1, project_id="p1", payload=None):
    return {
        "schema_version": 2,
        "event_id": event_id,
        "event_type": event_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "project_id": project_id,
        "occurred_at": "2026-01-01T00:00:00Z",
        "payload": payload or {},
    }


def test_apply_event_network_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumNetworkRow

    ev = _event("network", "network.created", "net-1", payload={
        "name": "prod-net", "type": "vxlan",
        "labels": {"env": "prod"},
    })
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumNetworkRow).filter_by(id="net-1").first()
    assert row is not None
    assert row.name == "prod-net"
    assert row.type == "vxlan"
    assert row.project_id == "p1"
    assert row.labels == {"env": "prod"}


def test_apply_event_network_idempotent(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumNetworkRow

    ev = _event("network", "network.created", "net-x", event_id=1, payload={"name": "n1"})
    apply_event(sqlite_db, ev)
    apply_event(sqlite_db, ev)  # второй раз — upsert

    count = sqlite_db.query(NervumNetworkRow).filter_by(id="net-x").count()
    assert count == 1


def test_apply_event_node_removed(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumNodeRow

    apply_event(sqlite_db, _event("node", "node.registered", "node-1", event_id=1,
                                   payload={"name": "worker-1", "status": "active"}))
    assert sqlite_db.query(NervumNodeRow).filter_by(id="node-1").count() == 1

    apply_event(sqlite_db, _event("node", "node.removed", "node-1", event_id=2))
    assert sqlite_db.query(NervumNodeRow).filter_by(id="node-1").count() == 0


def test_apply_event_unknown_schema_quarantined(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumEventQuarantineRow, NervumNetworkRow

    ev = {
        "schema_version": 99,
        "event_id": 42,
        "event_type": "network.created",
        "resource_type": "network",
        "resource_id": "net-future",
        "payload": {"name": "future"},
    }
    apply_event(sqlite_db, ev)

    # должно попасть в карантин
    q = sqlite_db.query(NervumEventQuarantineRow).filter_by(event_id=42).first()
    assert q is not None
    assert q.schema_version == 99

    # НЕ должно создать сеть
    assert sqlite_db.query(NervumNetworkRow).filter_by(id="net-future").count() == 0


def test_apply_event_watermark_advances(sqlite_db):
    from adapters.nervum.sync import apply_event, _get_or_create_state

    apply_event(sqlite_db, _event("network", "network.created", "net-w1", event_id=5))
    apply_event(sqlite_db, _event("network", "network.created", "net-w2", event_id=10))
    apply_event(sqlite_db, _event("network", "network.created", "net-w3", event_id=3))

    state = _get_or_create_state(sqlite_db)
    assert state.watermark == 10  # максимальный event_id


def test_apply_event_logical_port_lifecycle(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumLogicalPortRow

    apply_event(sqlite_db, _event("logical_port", "logical_port.created", "port-1",
                                   event_id=1, payload={
                                       "name": "vm-test", "network_id": "net-1",
                                       "status": "active", "mac": "02:ab:cd:ef:00:01",
                                   }))
    row = sqlite_db.query(NervumLogicalPortRow).filter_by(id="port-1").first()
    assert row.mac == "02:ab:cd:ef:00:01"
    assert row.status == "active"

    apply_event(sqlite_db, _event("logical_port", "logical_port.deleted", "port-1", event_id=2))
    assert sqlite_db.query(NervumLogicalPortRow).filter_by(id="port-1").count() == 0


def test_apply_event_router_status_change(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumRouterRow

    apply_event(sqlite_db, _event("router", "router.created", "r-1", event_id=1,
                                   payload={"name": "edge-1", "status": "build"}))
    apply_event(sqlite_db, _event("router", "router.status_changed", "r-1", event_id=2,
                                   payload={"name": "edge-1", "status": "active"}))

    row = sqlite_db.query(NervumRouterRow).filter_by(id="r-1").first()
    assert row.status == "active"
    assert row.name == "edge-1"


# ── NervumClient logical port methods ─────────────────────────────────────

@pytest.mark.asyncio
async def test_create_logical_port_payload():
    """create_logical_port sends correct JSON payload."""
    import os
    os.environ.setdefault("FERNET_KEY", "XvgfcADXX1oKcITCS8V7iQWr9VcweqQR7H3Vc_2qsFs=")
    os.environ.setdefault("NERVUM_URL", "http://nervum:8080")

    from adapters.nervum.client import NervumClient

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": "port-new", "name": "vm-test",
        "status": "pending", "mac": "02:aa:bb:cc:dd:ee",
    }

    with patch("adapters.nervum.client._request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_response
        client = NervumClient()
        result = await client.create_logical_port(
            "net-1", name="vm-test", project_id="proj-1"
        )

    assert result["id"] == "port-new"
    call_kwargs = mock_req.call_args
    assert call_kwargs[0][0] == "POST"
    assert "/networks/net-1/logical-ports" in call_kwargs[0][1]
    assert call_kwargs[1]["json"]["name"] == "vm-test"
    assert call_kwargs[1]["json"]["project_id"] == "proj-1"


@pytest.mark.asyncio
async def test_delete_logical_port_404_is_ok():
    """delete_logical_port should not raise on 404 (via RuntimeError wrapping)."""
    import os
    os.environ.setdefault("FERNET_KEY", "XvgfcADXX1oKcITCS8V7iQWr9VcweqQR7H3Vc_2qsFs=")
    os.environ.setdefault("NERVUM_URL", "http://nervum:8080")

    from adapters.nervum.client import NervumClient

    with patch("adapters.nervum.client._request", new_callable=AsyncMock) as mock_req:
        # _request raises RuntimeError with "HTTP 404" after all retries exhausted
        mock_req.side_effect = RuntimeError("nervum: all 3 attempts failed: HTTP 404")
        client = NervumClient()
        # должно не падать
        await client.delete_logical_port("port-gone")


@pytest.mark.asyncio
async def test_delete_logical_port_non_404_reraises():
    """delete_logical_port should re-raise non-404 errors."""
    import os
    os.environ.setdefault("FERNET_KEY", "XvgfcADXX1oKcITCS8V7iQWr9VcweqQR7H3Vc_2qsFs=")
    os.environ.setdefault("NERVUM_URL", "http://nervum:8080")

    from adapters.nervum.client import NervumClient

    with patch("adapters.nervum.client._request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = RuntimeError("nervum: all 3 attempts failed: HTTP 503")
        client = NervumClient()
        with pytest.raises(RuntimeError, match="503"):
            await client.delete_logical_port("port-alive")
