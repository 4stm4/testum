# SPDX-License-Identifier: MIT
"""Tests for /api/backup and /api/gitops endpoints."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_platform(client: TestClient, name: str, host: str = "10.0.0.1") -> str:
    resp = client.post(
        "/api/platforms/",
        json={
            "name": name,
            "host": host,
            "port": 22,
            "username": "ops",
            "auth_method": "password",
            "password": "s3cr3t",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _make_key(client: TestClient, name: str) -> str:
    resp = client.post(
        "/api/keys/",
        json={
            "name": name,
            "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC test-key",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# GET /api/backup/export
# ---------------------------------------------------------------------------

def test_export_returns_yaml(client: TestClient):
    """Export endpoint must return valid YAML with the required top-level keys."""
    resp = client.get("/api/backup/export")
    assert resp.status_code == 200
    assert "yaml" in resp.headers["content-type"]

    data = yaml.safe_load(resp.content)
    assert "metadata" in data
    assert "platforms" in data
    assert "ssh_keys" in data
    assert "users" in data


def test_export_metadata_fields(client: TestClient):
    """Metadata section must contain version and exported_at."""
    resp = client.get("/api/backup/export")
    assert resp.status_code == 200
    data = yaml.safe_load(resp.content)
    meta = data["metadata"]
    assert "version" in meta
    assert "exported_at" in meta


def test_export_includes_created_platform(client: TestClient):
    """A platform created before export should appear in the YAML."""
    _make_platform(client, "backup-plat", host="10.20.0.1")

    resp = client.get("/api/backup/export")
    assert resp.status_code == 200
    data = yaml.safe_load(resp.content)

    names = [p["name"] for p in data["platforms"]]
    assert "backup-plat" in names


def test_export_no_passwords(client: TestClient):
    """Exported YAML must not contain plaintext passwords or encrypted blobs."""
    _make_platform(client, "backup-nopass", host="10.20.0.2")

    resp = client.get("/api/backup/export")
    data = yaml.safe_load(resp.content)

    for plat in data["platforms"]:
        assert "password" not in plat
        assert "encrypted_password" not in plat


def test_export_includes_ssh_key(client: TestClient):
    """Public SSH keys should appear in the export."""
    _make_key(client, "backup-key")

    resp = client.get("/api/backup/export")
    data = yaml.safe_load(resp.content)

    names = [k["name"] for k in data["ssh_keys"]]
    assert "backup-key" in names


def test_export_no_hashed_passwords_in_users(client: TestClient):
    """User entries must not contain hashed_password."""
    resp = client.get("/api/backup/export")
    data = yaml.safe_load(resp.content)

    for u in data["users"]:
        assert "hashed_password" not in u
        assert "password" not in u


# ---------------------------------------------------------------------------
# POST /api/backup/import
# ---------------------------------------------------------------------------

def _make_backup_yaml(platforms=None, ssh_keys=None, users=None) -> bytes:
    data = {
        "metadata": {"version": "0.1.0", "exported_at": "2025-01-01T00:00:00"},
        "platforms": platforms or [],
        "ssh_keys": ssh_keys or [],
        "users": users or [],
    }
    return yaml.dump(data).encode()


def test_import_creates_platform(client: TestClient):
    """Valid YAML import should create a new platform."""
    payload = _make_backup_yaml(
        platforms=[
            {
                "name": "imported-plat",
                "host": "10.30.0.1",
                "port": 22,
                "username": "root",
                "auth_method": "password",
            }
        ]
    )
    resp = client.post(
        "/api/backup/import",
        content=payload,
        headers={"Content-Type": "application/x-yaml"},
    )
    assert resp.status_code == 200
    stats = resp.json()["stats"]
    assert stats["platforms_imported"] == 1

    # Verify it actually exists in the DB
    list_resp = client.get("/api/platforms/")
    names = [p["name"] for p in list_resp.json()]
    assert "imported-plat" in names


def test_import_skips_duplicate_platform(client: TestClient):
    """Importing a platform that already exists should skip it, not error."""
    _make_platform(client, "dup-plat", host="10.30.0.2")

    payload = _make_backup_yaml(
        platforms=[
            {
                "name": "dup-plat",
                "host": "10.30.0.2",
                "port": 22,
                "username": "root",
                "auth_method": "password",
            }
        ]
    )
    resp = client.post(
        "/api/backup/import",
        content=payload,
        headers={"Content-Type": "application/x-yaml"},
    )
    assert resp.status_code == 200
    stats = resp.json()["stats"]
    assert stats["platforms_imported"] == 0
    assert any("already exists" in e for e in stats["errors"])


def test_import_creates_ssh_key(client: TestClient):
    """SSH keys present in YAML should be imported."""
    payload = _make_backup_yaml(
        ssh_keys=[
            {
                "name": "imported-key",
                "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC imported",
            }
        ]
    )
    resp = client.post(
        "/api/backup/import",
        content=payload,
        headers={"Content-Type": "application/x-yaml"},
    )
    assert resp.status_code == 200
    assert resp.json()["stats"]["ssh_keys_imported"] == 1


def test_import_rejects_invalid_yaml(client: TestClient):
    """Sending garbage bytes should return 400."""
    resp = client.post(
        "/api/backup/import",
        content=b"not: valid: yaml: [[[",
        headers={"Content-Type": "application/x-yaml"},
    )
    assert resp.status_code == 400


def test_import_rejects_non_dict_yaml(client: TestClient):
    """YAML that is a list (not a dict) should return 400."""
    resp = client.post(
        "/api/backup/import",
        content=yaml.dump(["just", "a", "list"]).encode(),
        headers={"Content-Type": "application/x-yaml"},
    )
    assert resp.status_code == 400


def test_import_users_blocked(client: TestClient):
    """User import must be refused for security reasons."""
    payload = _make_backup_yaml(
        users=[{"username": "hacker", "role": "admin", "is_active": True}]
    )
    resp = client.post(
        "/api/backup/import",
        content=payload,
        headers={"Content-Type": "application/x-yaml"},
    )
    assert resp.status_code == 200
    errors = resp.json()["stats"]["errors"]
    assert any("not supported" in e.lower() or "security" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# POST /api/gitops/import — helpers
# ---------------------------------------------------------------------------

def _gitops_config_yaml(platforms=None, ssh_keys=None) -> str:
    data: dict = {}
    if platforms:
        data["platforms"] = platforms
    if ssh_keys:
        data["ssh_keys"] = ssh_keys
    return yaml.dump(data)


def _fake_clone(config_content: str, filename: str = "testum-config.yaml"):
    """Return a context that patches clone_git_repo to write config_content to a temp dir."""
    def _clone(git_url, branch="main", username=None, token=None):
        tmp = Path(tempfile.mkdtemp(prefix="fake_clone_"))
        (tmp / filename).write_text(config_content)
        return tmp

    return patch("app.api.gitops.clone_git_repo", side_effect=_clone)


# ---------------------------------------------------------------------------
# POST /api/gitops/import
# ---------------------------------------------------------------------------

def test_gitops_import_missing_git_url(client: TestClient):
    """Request without git_url must return 400."""
    resp = client.post("/api/gitops/import", json={"branch": "main"})
    assert resp.status_code == 400
    assert "git_url" in resp.json()["error"]


def test_gitops_import_clone_failure(client: TestClient):
    """If git clone fails the endpoint should return 400."""
    with patch(
        "app.api.gitops.clone_git_repo",
        side_effect=ValueError("Git clone failed: repository not found"),
    ):
        resp = client.post(
            "/api/gitops/import",
            json={"git_url": "https://github.com/none/none.git"},
        )
    assert resp.status_code == 400
    assert "clone" in resp.json()["error"].lower() or "git" in resp.json()["error"].lower()


def test_gitops_import_config_not_found(client: TestClient):
    """If no config file exists in the repo the endpoint should return 404."""

    def _clone_empty(git_url, branch="main", username=None, token=None):
        return Path(tempfile.mkdtemp(prefix="fake_empty_"))

    with patch("app.api.gitops.clone_git_repo", side_effect=_clone_empty):
        resp = client.post(
            "/api/gitops/import",
            json={"git_url": "https://github.com/none/none.git"},
        )
    assert resp.status_code == 404
    assert "not found" in resp.json()["error"].lower()


def test_gitops_import_creates_platform(client: TestClient):
    """Valid config in a cloned repo should import platforms."""
    config_yaml = _gitops_config_yaml(
        platforms=[
            {
                "name": "gitops-plat",
                "host": "10.50.0.1",
                "port": 22,
                "username": "deploy",
                "auth_method": "password",
            }
        ]
    )
    with _fake_clone(config_yaml):
        resp = client.post(
            "/api/gitops/import",
            json={"git_url": "https://github.com/example/infra.git"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["platforms_imported"] == 1

    names = [p["name"] for p in client.get("/api/platforms/").json()]
    assert "gitops-plat" in names


def test_gitops_import_dry_run_no_persist(client: TestClient):
    """dry_run=true should report stats but not create anything in DB."""
    config_yaml = _gitops_config_yaml(
        platforms=[
            {
                "name": "dry-run-plat",
                "host": "10.50.0.2",
                "port": 22,
                "username": "deploy",
                "auth_method": "password",
            }
        ]
    )
    with _fake_clone(config_yaml):
        resp = client.post(
            "/api/gitops/import",
            json={
                "git_url": "https://github.com/example/infra.git",
                "dry_run": True,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    assert data["platforms_imported"] == 1

    # Must NOT actually exist in DB
    names = [p["name"] for p in client.get("/api/platforms/").json()]
    assert "dry-run-plat" not in names


def test_gitops_import_skips_duplicate(client: TestClient):
    """Platform that already exists in DB should be skipped without error."""
    _make_platform(client, "existing-gitops", host="10.50.0.3")

    config_yaml = _gitops_config_yaml(
        platforms=[
            {
                "name": "existing-gitops",
                "host": "10.50.0.3",
                "port": 22,
                "username": "deploy",
                "auth_method": "password",
            }
        ]
    )
    with _fake_clone(config_yaml):
        resp = client.post(
            "/api/gitops/import",
            json={"git_url": "https://github.com/example/infra.git"},
        )

    assert resp.status_code == 200
    assert resp.json()["platforms_skipped"] == 1
    assert resp.json()["platforms_imported"] == 0


def test_gitops_import_with_ssh_key(client: TestClient):
    """SSH keys in config should be imported before platforms."""
    config_yaml = _gitops_config_yaml(
        ssh_keys=[
            {
                "name": "gitops-key",
                "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC gitops",
            }
        ],
        platforms=[
            {
                "name": "gitops-key-plat",
                "host": "10.50.0.4",
                "port": 22,
                "username": "deploy",
                "auth_method": "key",
                "ssh_key_name": "gitops-key",
            }
        ],
    )
    with _fake_clone(config_yaml):
        resp = client.post(
            "/api/gitops/import",
            json={"git_url": "https://github.com/example/infra.git"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ssh_keys_imported"] == 1
    assert data["platforms_imported"] == 1


def test_gitops_import_alternative_config_path(client: TestClient):
    """Endpoint should find testum.yaml when testum-config.yaml is absent."""
    config_yaml = _gitops_config_yaml(
        platforms=[
            {
                "name": "alt-path-plat",
                "host": "10.50.0.5",
                "port": 22,
                "username": "deploy",
                "auth_method": "password",
            }
        ]
    )

    def _clone_alt(git_url, branch="main", username=None, token=None):
        tmp = Path(tempfile.mkdtemp(prefix="fake_alt_"))
        (tmp / "testum.yaml").write_text(config_yaml)   # alternative name
        return tmp

    with patch("app.api.gitops.clone_git_repo", side_effect=_clone_alt):
        resp = client.post(
            "/api/gitops/import",
            json={"git_url": "https://github.com/example/infra.git"},
        )

    assert resp.status_code == 200
    assert resp.json()["platforms_imported"] == 1
