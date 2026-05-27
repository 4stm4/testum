# SPDX-License-Identifier: MIT
"""Integration tests for the Users REST API (/api/users)."""
from __future__ import annotations

import uuid

import pytest
from starlette.testclient import TestClient


# ── helpers ───────────────────────────────────────────────────────────────────

def _create_user(client: TestClient, username: str, password: str = "Pass1234!",
                 role: str = "viewer", email: str | None = None) -> dict:
    payload: dict = {"username": username, "password": password, "role": role}
    if email is not None:
        payload["email"] = email
    r = client.post("/api/users/", json=payload)
    return r


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_users_returns_paginated_response(client: TestClient, test_db):
    r = client.get("/api/users/")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["items"], list)
    # At least the seeded admin user must be present
    assert data["total"] >= 1


def test_list_users_x_total_count_header(client: TestClient, test_db):
    r = client.get("/api/users/")
    assert r.status_code == 200
    assert "x-total-count" in r.headers
    assert int(r.headers["x-total-count"]) >= 1


def test_list_users_pagination_limit_offset(client: TestClient, test_db):
    # Create two extra users so we have at least 3 total
    _create_user(client, "pag_user1")
    _create_user(client, "pag_user2")

    r = client.get("/api/users/?limit=1&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    assert data["limit"] == 1
    assert data["offset"] == 0


def test_list_users_unauthenticated_returns_401(test_db):
    from app.main import app
    with TestClient(app) as bare:
        r = bare.get("/api/users/")
    assert r.status_code == 401


# ── create ────────────────────────────────────────────────────────────────────

def test_create_user_success(client: TestClient, test_db):
    r = _create_user(client, "newuser")
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "newuser"
    assert "id" in data
    assert "hashed_password" not in data


def test_create_user_with_email(client: TestClient, test_db):
    r = _create_user(client, "userwithemail", email="user@example.com")
    assert r.status_code == 201
    assert r.json()["email"] == "user@example.com"


def test_create_user_operator_role(client: TestClient, test_db):
    r = _create_user(client, "op_user", role="operator")
    assert r.status_code == 201
    assert r.json()["role"] == "operator"


def test_create_user_duplicate_username_returns_409(client: TestClient, test_db):
    _create_user(client, "dupuser")
    r = _create_user(client, "dupuser")
    assert r.status_code == 409
    assert "error" in r.json()


def test_create_user_duplicate_email_returns_409(client: TestClient, test_db):
    _create_user(client, "email_user1", email="dup@example.com")
    r = _create_user(client, "email_user2", email="dup@example.com")
    assert r.status_code == 409
    assert "error" in r.json()


# ── me ────────────────────────────────────────────────────────────────────────

def test_get_current_user_me(client: TestClient, test_db):
    r = client.get("/api/users/me")
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert "username" in data
    # The fixture logs in as admin
    assert data["role"] == "admin"


# ── get by id ─────────────────────────────────────────────────────────────────

def test_get_user_by_id(client: TestClient, test_db):
    create_r = _create_user(client, "fetchme")
    assert create_r.status_code == 201
    user_id = create_r.json()["id"]

    r = client.get(f"/api/users/{user_id}")
    assert r.status_code == 200
    assert r.json()["id"] == user_id
    assert r.json()["username"] == "fetchme"


def test_get_user_not_found_returns_404(client: TestClient, test_db):
    r = client.get(f"/api/users/{uuid.uuid4()}")
    assert r.status_code == 404
    assert "error" in r.json()


# ── update ────────────────────────────────────────────────────────────────────

def test_update_user_username(client: TestClient, test_db):
    user_id = _create_user(client, "before_rename").json()["id"]
    r = client.put(f"/api/users/{user_id}", json={"username": "after_rename"})
    assert r.status_code == 200
    assert r.json()["username"] == "after_rename"


def test_update_user_password_changes_hash(client: TestClient, test_db):
    from app.security import hash_password

    user_id = _create_user(client, "pw_user", password="OldPass1!").json()["id"]

    # Fetch current hash via DB
    from app.models import User
    old_hash = test_db.query(User).filter(User.id == user_id).first().hashed_password

    r = client.put(f"/api/users/{user_id}", json={"password": "NewPass2!"})
    assert r.status_code == 200

    test_db.expire_all()
    new_hash = test_db.query(User).filter(User.id == user_id).first().hashed_password
    assert old_hash != new_hash


def test_update_user_role(client: TestClient, test_db):
    user_id = _create_user(client, "role_user", role="viewer").json()["id"]
    r = client.put(f"/api/users/{user_id}", json={"role": "operator"})
    assert r.status_code == 200
    assert r.json()["role"] == "operator"


def test_update_user_deactivate(client: TestClient, test_db):
    user_id = _create_user(client, "deact_user").json()["id"]
    r = client.put(f"/api/users/{user_id}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_update_user_cannot_deactivate_self(client: TestClient, test_db):
    # Get the admin user id from /me
    me = client.get("/api/users/me").json()
    r = client.put(f"/api/users/{me['id']}", json={"is_active": False})
    assert r.status_code == 400
    assert "error" in r.json()


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_user_success(client: TestClient, test_db):
    user_id = _create_user(client, "todelete").json()["id"]
    r = client.delete(f"/api/users/{user_id}")
    assert r.status_code == 200

    # Confirm gone
    r2 = client.get(f"/api/users/{user_id}")
    assert r2.status_code == 404


def test_delete_user_not_found_returns_404(client: TestClient, test_db):
    r = client.delete(f"/api/users/{uuid.uuid4()}")
    assert r.status_code == 404
    assert "error" in r.json()


def test_delete_user_cannot_delete_self(client: TestClient, test_db):
    me = client.get("/api/users/me").json()
    r = client.delete(f"/api/users/{me['id']}")
    assert r.status_code == 400
    assert "error" in r.json()
