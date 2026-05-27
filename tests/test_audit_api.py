# SPDX-License-Identifier: MIT
"""Integration tests for the Audit API (/api/audit)."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta

import pytest
from starlette.testclient import TestClient


# ── helpers ───────────────────────────────────────────────────────────────────

def _seed(db, user: str = "admin", action: str = "create",
          object_type: str = "platform", object_id: str = "plat-1",
          meta: dict | None = None):
    from app.audit import log_audit
    return log_audit(db, user=user, action=action, object_type=object_type,
                     object_id=object_id, meta=meta)


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_audit_logs_empty(client: TestClient, test_db):
    r = client.get("/api/audit/")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_audit_logs_returns_entries(client: TestClient, test_db):
    _seed(test_db)
    r = client.get("/api/audit/")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    entry = data[0]
    assert "id" in entry
    assert "user" in entry
    assert "action" in entry
    assert "timestamp" in entry


def test_list_audit_logs_filter_by_user(client: TestClient, test_db):
    _seed(test_db, user="alice", action="delete", object_type="vm")
    _seed(test_db, user="bob", action="create", object_type="network")

    r = client.get("/api/audit/?user=alice")
    assert r.status_code == 200
    data = r.json()
    assert all(e["user"] == "alice" for e in data)
    assert len(data) >= 1


def test_list_audit_logs_filter_by_action(client: TestClient, test_db):
    _seed(test_db, user="admin", action="delete", object_type="platform")
    _seed(test_db, user="admin", action="update", object_type="platform")

    r = client.get("/api/audit/?action=delete")
    assert r.status_code == 200
    data = r.json()
    assert all(e["action"] == "delete" for e in data)


def test_list_audit_logs_filter_by_object_type(client: TestClient, test_db):
    _seed(test_db, user="admin", action="create", object_type="vm")
    _seed(test_db, user="admin", action="create", object_type="network")

    r = client.get("/api/audit/?object_type=vm")
    assert r.status_code == 200
    data = r.json()
    assert all(e["object_type"] == "vm" for e in data)
    assert len(data) >= 1


def test_list_audit_logs_x_total_count_header(client: TestClient, test_db):
    _seed(test_db)
    _seed(test_db, action="update")
    r = client.get("/api/audit/")
    assert r.status_code == 200
    assert "x-total-count" in r.headers
    assert int(r.headers["x-total-count"]) >= 2


def test_list_audit_logs_pagination(client: TestClient, test_db):
    for i in range(5):
        _seed(test_db, action=f"action_{i}", object_id=f"obj-{i}")

    r = client.get("/api/audit/?limit=2&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2


def test_list_audit_logs_days_filter(client: TestClient, test_db):
    from app.models import AuditLog

    # Seed an old entry by directly setting the timestamp
    old_entry = AuditLog(
        user="olduser",
        action="old_action",
        object_type="platform",
        object_id="old-1",
        timestamp=datetime.utcnow() - timedelta(days=10),
    )
    test_db.add(old_entry)
    test_db.commit()

    # Seed a recent entry
    _seed(test_db, user="newuser", action="new_action")

    # With days=1 the old entry should not appear
    r = client.get("/api/audit/?days=1")
    assert r.status_code == 200
    data = r.json()
    users = [e["user"] for e in data]
    assert "olduser" not in users
    assert "newuser" in users


# ── stats ─────────────────────────────────────────────────────────────────────

def test_audit_stats_returns_totals(client: TestClient, test_db):
    _seed(test_db)
    r = client.get("/api/audit/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total_actions" in data
    assert "period_days" in data
    assert data["total_actions"] >= 1


def test_audit_stats_actions_by_type(client: TestClient, test_db):
    _seed(test_db, action="create")
    _seed(test_db, action="delete", object_id="plat-2")

    r = client.get("/api/audit/stats")
    assert r.status_code == 200
    data = r.json()
    assert "actions_by_type" in data
    abt = data["actions_by_type"]
    assert isinstance(abt, dict)
    assert "create" in abt
    assert "delete" in abt


def test_audit_stats_top_users(client: TestClient, test_db):
    _seed(test_db, user="alice")
    _seed(test_db, user="alice", action="delete", object_id="plat-2")
    _seed(test_db, user="bob")

    r = client.get("/api/audit/stats")
    assert r.status_code == 200
    data = r.json()
    assert "top_users" in data
    top = data["top_users"]
    assert isinstance(top, list)
    usernames = [entry["user"] for entry in top]
    assert "alice" in usernames


# ── export ────────────────────────────────────────────────────────────────────

def test_export_json_format(client: TestClient, test_db):
    _seed(test_db)
    r = client.get("/api/audit/export?format=json")
    assert r.status_code == 200
    disposition = r.headers.get("content-disposition", "")
    assert ".json" in disposition

    # Verify body parses as valid JSON list
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "id" in data[0]


def test_export_csv_format(client: TestClient, test_db):
    _seed(test_db)
    r = client.get("/api/audit/export?format=csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")

    # Verify CSV has header row
    text = r.text
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    assert len(rows) >= 2  # header + at least one data row
    header = [col.strip() for col in rows[0]]
    assert "ID" in header
    assert "User" in header
    assert "Action" in header


def test_export_invalid_format_returns_400(client: TestClient, test_db):
    r = client.get("/api/audit/export?format=invalid")
    assert r.status_code == 400
    assert "error" in r.json()


# ── meta ──────────────────────────────────────────────────────────────────────

def test_audit_log_includes_meta(client: TestClient, test_db):
    meta = {"detail": "test run", "count": 3}
    _seed(test_db, meta=meta)

    r = client.get("/api/audit/")
    assert r.status_code == 200
    data = r.json()
    # Find the entry we seeded
    entry = next((e for e in data if e.get("meta") is not None), None)
    assert entry is not None
    assert entry["meta"]["detail"] == "test run"
    assert entry["meta"]["count"] == 3
