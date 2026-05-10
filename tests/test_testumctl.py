# SPDX-License-Identifier: MIT
"""Tests for testumctl CLI client."""
import argparse
import json
import sys
import types
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Import testumctl as a module (it lives at repo root, no .py extension)
# ---------------------------------------------------------------------------
import importlib.machinery, importlib.util, pathlib

_ctl_path = str(pathlib.Path(__file__).parent.parent / "testumctl")
_loader = importlib.machinery.SourceFileLoader("testumctl", _ctl_path)
_spec = importlib.util.spec_from_loader("testumctl", _loader)
_mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(_mod)

TestumClient = _mod.TestumClient
ConfigManager = _mod.ConfigManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(json_data=None, status_code=200, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or (json.dumps(json_data) if json_data else "")
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    return resp


def _client(token="test-token"):
    return TestumClient("http://testum.local", token=token)


# ---------------------------------------------------------------------------
# TestumClient — auth
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_returns_token(self):
        client = TestumClient("http://testum.local")
        resp = _mock_response({"access_token": "my-jwt"})
        client.session.post = MagicMock(return_value=resp)

        token = client.login("admin", "secret")

        assert token == "my-jwt"
        assert client.token == "my-jwt"
        client.session.post.assert_called_once_with(
            "http://testum.local/api/auth/login",
            json={"username": "admin", "password": "secret"},
        )

    def test_login_raises_on_http_error(self):
        client = TestumClient("http://testum.local")
        resp = _mock_response(status_code=401)
        resp.raise_for_status.side_effect = Exception("401 Unauthorized")
        client.session.post = MagicMock(return_value=resp)

        with pytest.raises(Exception, match="401"):
            client.login("admin", "wrong")


# ---------------------------------------------------------------------------
# TestumClient — platforms
# ---------------------------------------------------------------------------

class TestPlatforms:
    def test_list_platforms(self):
        c = _client()
        data = [{"id": "1", "name": "prod", "host": "10.0.0.1"}]
        c.session.get = MagicMock(return_value=_mock_response(data))

        result = c.list_platforms()

        assert result == data
        c.session.get.assert_called_once()
        url = c.session.get.call_args[0][0]
        assert "/api/platforms/" in url

    def test_create_platform(self):
        c = _client()
        payload = {"name": "staging", "host": "10.0.0.2", "username": "ubuntu", "auth_method": "password"}
        created = {**payload, "id": "abc"}
        c.session.post = MagicMock(return_value=_mock_response(created))

        result = c.create_platform(payload)

        assert result["id"] == "abc"
        c.session.post.assert_called_once()

    def test_delete_platform(self):
        c = _client()
        c.session.delete = MagicMock(return_value=_mock_response({}))

        c.delete_platform("abc-123")

        c.session.delete.assert_called_once()
        assert "abc-123" in c.session.delete.call_args[0][0]

    def test_refresh_platform_info(self):
        c = _client()
        c.session.post = MagicMock(return_value=_mock_response({"status": "queued", "task_id": "t1"}))

        result = c.refresh_platform_info("p-1")

        assert result["status"] == "queued"
        assert "refresh-info" in c.session.post.call_args[0][0]


# ---------------------------------------------------------------------------
# TestumClient — scripts
# ---------------------------------------------------------------------------

class TestScripts:
    def test_list_scripts(self):
        c = _client()
        data = [{"id": "s1", "name": "deploy.sh", "language": "bash"}]
        c.session.get = MagicMock(return_value=_mock_response(data))

        result = c.list_scripts()

        assert result == data

    def test_create_script(self):
        c = _client()
        payload = {"name": "setup.sh", "language": "bash", "content": "#!/bin/bash\necho hi"}
        created = {**payload, "id": "s2"}
        c.session.post = MagicMock(return_value=_mock_response(created))

        result = c.create_script(payload)

        assert result["id"] == "s2"

    def test_delete_script(self):
        c = _client()
        c.session.delete = MagicMock(return_value=_mock_response({}))

        c.delete_script("s1")

        assert "s1" in c.session.delete.call_args[0][0]

    def test_run_script(self):
        c = _client()
        c.session.post = MagicMock(return_value=_mock_response({"task_id": "t2"}))

        result = c.run_script("p1", "s1")

        assert result["task_id"] == "t2"
        url = c.session.post.call_args[0][0]
        assert "p1" in url
        assert "run_command" in url


# ---------------------------------------------------------------------------
# TestumClient — automations
# ---------------------------------------------------------------------------

class TestAutomations:
    def test_list_automations(self):
        c = _client()
        data = [{"id": "j1", "name": "nightly", "is_enabled": True}]
        c.session.get = MagicMock(return_value=_mock_response(data))

        result = c.list_automations()

        assert result == data

    def test_update_automation(self):
        c = _client()
        c.session.put = MagicMock(return_value=_mock_response({"id": "j1", "is_enabled": False}))

        result = c.update_automation("j1", {"is_enabled": False})

        assert result["is_enabled"] is False
        assert "j1" in c.session.put.call_args[0][0]

    def test_run_automation(self):
        c = _client()
        c.session.post = MagicMock(return_value=_mock_response({"task_id": "t3", "status": "queued"}))

        result = c.run_automation("j1")

        assert result["task_id"] == "t3"
        assert "run" in c.session.post.call_args[0][0]

    def test_delete_automation(self):
        c = _client()
        c.session.delete = MagicMock(return_value=_mock_response({}))

        c.delete_automation("j1")

        assert "j1" in c.session.delete.call_args[0][0]


# ---------------------------------------------------------------------------
# TestumClient — tasks
# ---------------------------------------------------------------------------

class TestTasks:
    def test_get_task(self):
        c = _client()
        data = {"id": "t1", "status": "success"}
        c.session.get = MagicMock(return_value=_mock_response(data))

        result = c.get_task("t1")

        assert result["status"] == "success"
        assert "t1" in c.session.get.call_args[0][0]

    def test_revoke_task(self):
        c = _client()
        c.session.post = MagicMock(return_value=_mock_response({"message": "revoked"}))

        result = c.revoke_task("t1")

        assert "revoked" in result.get("message", "")


# ---------------------------------------------------------------------------
# TestumClient — audit
# ---------------------------------------------------------------------------

class TestAudit:
    def test_list_audit(self):
        c = _client()
        data = [{"id": "a1", "action": "login", "username": "admin"}]
        c.session.get = MagicMock(return_value=_mock_response(data))

        result = c.list_audit()

        assert result == data
        url = c.session.get.call_args[0][0]
        assert "/api/audit/" in url

    def test_list_audit_with_action_filter(self):
        c = _client()
        c.session.get = MagicMock(return_value=_mock_response([]))

        c.list_audit(action="login")

        params = c.session.get.call_args[1].get("params", {})
        assert params.get("action") == "login"

    def test_audit_stats(self):
        c = _client()
        data = {"total": 42, "by_action": {"login": 10}}
        c.session.get = MagicMock(return_value=_mock_response(data))

        result = c.audit_stats()

        assert result["total"] == 42


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------

class TestConfigManager:
    def test_load_returns_empty_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod.Path, "home", lambda: tmp_path)
        mgr = ConfigManager()
        mgr.config_path = tmp_path / "nonexistent.json"

        cfg = mgr.load()

        assert cfg == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        mgr = ConfigManager()
        mgr.config_path = tmp_path / "config.json"
        mgr.config_path.parent.mkdir(parents=True, exist_ok=True)

        mgr.save({"url": "http://testum.local", "token": "abc"})
        loaded = mgr.load()

        assert loaded["url"] == "http://testum.local"
        assert loaded["token"] == "abc"


# ---------------------------------------------------------------------------
# CLI command functions
# ---------------------------------------------------------------------------

class TestCmdPlatformsList:
    def test_prints_table(self, capsys):
        c = _client()
        c.list_platforms = MagicMock(return_value=[
            {"id": "1", "name": "prod", "host": "10.0.0.1", "username": "ubuntu",
             "auth_method": "password", "is_enabled": True}
        ])
        args = argparse.Namespace(json=False, limit=100, offset=0)

        _mod.cmd_platforms_list(args, c)

        out = capsys.readouterr().out
        assert "prod" in out
        assert "10.0.0.1" in out

    def test_json_output(self, capsys):
        c = _client()
        c.list_platforms = MagicMock(return_value=[{"id": "1", "name": "prod"}])
        args = argparse.Namespace(json=True, limit=100, offset=0)

        _mod.cmd_platforms_list(args, c)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data[0]["name"] == "prod"


class TestCmdAutomationsList:
    def test_prints_table(self, capsys):
        c = _client()
        c.list_automations = MagicMock(return_value=[
            {"id": "j1", "name": "nightly", "trigger_type": "cron",
             "is_enabled": True, "last_run_at": None}
        ])
        args = argparse.Namespace(json=False, limit=100, offset=0)

        _mod.cmd_automations_list(args, c)

        out = capsys.readouterr().out
        assert "nightly" in out


class TestCmdAuditList:
    def test_prints_table(self, capsys):
        c = _client()
        c.list_audit = MagicMock(return_value=[
            {"id": "a1", "username": "admin", "action": "login",
             "resource_type": "session", "resource_id": None, "timestamp": "2026-01-01T00:00:00"}
        ])
        args = argparse.Namespace(json=False, limit=50, offset=0, action=None)

        _mod.cmd_audit_list(args, c)

        out = capsys.readouterr().out
        assert "admin" in out
        assert "login" in out
