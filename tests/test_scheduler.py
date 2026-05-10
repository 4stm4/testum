# SPDX-License-Identifier: MIT
"""Tests for the automation scheduler and related endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# calc_next_run
# ---------------------------------------------------------------------------

def test_calc_next_run_basic():
    """Next run should be in the future."""
    from app.scheduler import calc_next_run

    base = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    # "every minute" cron
    nxt = calc_next_run("* * * * *", base)
    assert nxt > base


def test_calc_next_run_midnight():
    """Daily midnight cron should advance to the next occurrence."""
    from app.scheduler import calc_next_run

    base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    nxt = calc_next_run("0 0 * * *", base)
    # Must be after base and at midnight
    assert nxt > base
    assert nxt.hour == 0
    assert nxt.minute == 0


def test_calc_next_run_naive_base():
    """calc_next_run should work with a naive datetime base."""
    from app.scheduler import calc_next_run

    base = datetime(2025, 1, 1, 0, 0, 0)  # naive
    nxt = calc_next_run("0 3 * * *", base)
    assert nxt > base.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Automation job: next_run_at is set on create
# ---------------------------------------------------------------------------

def test_create_cron_job_sets_next_run_at(client: TestClient):
    """Creating a CRON automation job should populate next_run_at."""
    platform_resp = client.post(
        "/api/platforms/",
        json={
            "name": "sched-platform",
            "host": "10.0.0.1",
            "port": 22,
            "username": "ops",
            "auth_method": "password",
            "password": "s3cr3tXYZ",
        },
    )
    assert platform_resp.status_code == 201
    pid = platform_resp.json()["id"]

    job_resp = client.post(
        "/api/automations/",
        json={
            "name": "nightly-cron",
            "execution_type": "command",
            "command": "uptime",
            "trigger_type": "cron",
            "cron_expression": "0 3 * * *",
            "run_on_all_platforms": False,
            "target_platform_ids": [pid],
            "timeout_seconds": 120,
            "max_retries": 0,
            "retry_delay_seconds": 60,
            "is_enabled": True,
        },
    )
    assert job_resp.status_code == 201
    data = job_resp.json()
    assert data["next_run_at"] is not None, "next_run_at must be set for CRON jobs"


def test_create_manual_job_no_next_run_at(client: TestClient):
    """Manual trigger jobs should not have next_run_at set."""
    platform_resp = client.post(
        "/api/platforms/",
        json={
            "name": "manual-platform",
            "host": "10.0.0.2",
            "port": 22,
            "username": "ops",
            "auth_method": "password",
            "password": "s3cr3tXYZ",
        },
    )
    assert platform_resp.status_code == 201
    pid = platform_resp.json()["id"]

    job_resp = client.post(
        "/api/automations/",
        json={
            "name": "manual-job",
            "execution_type": "command",
            "command": "hostname",
            "trigger_type": "manual",
            "run_on_all_platforms": False,
            "target_platform_ids": [pid],
            "timeout_seconds": 60,
            "max_retries": 0,
            "retry_delay_seconds": 60,
            "is_enabled": True,
        },
    )
    assert job_resp.status_code == 201
    assert job_resp.json()["next_run_at"] is None


# ---------------------------------------------------------------------------
# POST /api/automations/{id}/run — manual dispatch
# ---------------------------------------------------------------------------

def _create_manual_job(client: TestClient, name: str = "run-job-test") -> tuple[str, str]:
    """Helper: create platform + automation job; return (job_id, platform_id)."""
    p = client.post(
        "/api/platforms/",
        json={
            "name": f"plat-{name}",
            "host": "10.1.0.1",
            "port": 22,
            "username": "ops",
            "auth_method": "password",
            "password": "s3cr3tXYZ",
        },
    )
    assert p.status_code == 201
    pid = p.json()["id"]

    j = client.post(
        "/api/automations/",
        json={
            "name": name,
            "execution_type": "command",
            "command": "echo hello",
            "trigger_type": "manual",
            "run_on_all_platforms": False,
            "target_platform_ids": [pid],
            "timeout_seconds": 30,
            "max_retries": 0,
            "retry_delay_seconds": 60,
            "is_enabled": True,
        },
    )
    assert j.status_code == 201
    return j.json()["id"], pid


def test_run_job_dispatches_tasks(client: TestClient):
    """POST /run on a valid job should enqueue tasks for each target platform."""
    job_id, _ = _create_manual_job(client, "dispatch-test")

    with patch(
        "app.scheduler.dispatch_automation_job",
        new_callable=AsyncMock,
        return_value=["fake-pyjobkit-id-1"],
    ):
        resp = client.post(f"/api/automations/{job_id}/run")

    assert resp.status_code == 200
    data = resp.json()
    assert data["enqueued_jobs"] == ["fake-pyjobkit-id-1"]
    assert "1 task" in data["message"]


def test_run_job_not_found(client: TestClient):
    resp = client.post(f"/api/automations/{uuid.uuid4()}/run")
    assert resp.status_code == 404


def test_run_job_disabled(client: TestClient):
    """Disabled jobs should be rejected."""
    job_id, _ = _create_manual_job(client, "disabled-run-test")
    # Disable it
    client.put(f"/api/automations/{job_id}", json={"is_enabled": False})

    resp = client.post(f"/api/automations/{job_id}/run")
    assert resp.status_code == 400
    assert "disabled" in resp.json()["error"].lower()


# ---------------------------------------------------------------------------
# POST /api/automations/webhook/{id}
# ---------------------------------------------------------------------------

def _create_webhook_job(client: TestClient, secret: str | None = None) -> str:
    p = client.post(
        "/api/platforms/",
        json={
            "name": f"wh-plat-{uuid.uuid4().hex[:6]}",
            "host": "10.2.0.1",
            "port": 22,
            "username": "ops",
            "auth_method": "password",
            "password": "s3cr3tXYZ",
        },
    )
    pid = p.json()["id"]

    payload = {
        "name": f"wh-job-{uuid.uuid4().hex[:6]}",
        "execution_type": "command",
        "command": "date",
        "trigger_type": "webhook",
        "run_on_all_platforms": False,
        "target_platform_ids": [pid],
        "timeout_seconds": 30,
        "max_retries": 0,
        "retry_delay_seconds": 60,
        "is_enabled": True,
    }
    if secret:
        payload["webhook_secret"] = secret

    j = client.post("/api/automations/", json=payload)
    assert j.status_code == 201, f"Expected 201, got {j.status_code}: {j.json()}"
    return j.json()["id"]


def test_webhook_no_secret_accepts(client: TestClient):
    """Webhook jobs with a secret should accept matching Bearer token."""
    job_id = _create_webhook_job(client, secret="open-token")

    with patch(
        "app.scheduler.dispatch_automation_job",
        new_callable=AsyncMock,
        return_value=["wh-job-id"],
    ):
        resp = client.post(
            f"/api/automations/webhook/{job_id}",
            headers={"Authorization": "Bearer open-token"},
        )

    assert resp.status_code == 200
    assert resp.json()["enqueued_jobs"] == ["wh-job-id"]


def test_webhook_bearer_auth_valid(client: TestClient):
    """Webhook with Bearer token matching webhook_secret should succeed."""
    job_id = _create_webhook_job(client, secret="my-secret-token")

    with patch(
        "app.scheduler.dispatch_automation_job",
        new_callable=AsyncMock,
        return_value=["wh-job-id"],
    ):
        resp = client.post(
            f"/api/automations/webhook/{job_id}",
            headers={"Authorization": "Bearer my-secret-token"},
        )

    assert resp.status_code == 200


def test_webhook_bearer_auth_invalid(client: TestClient):
    """Wrong Bearer token should be rejected with 401."""
    job_id = _create_webhook_job(client, secret="correct-secret")

    resp = client.post(
        f"/api/automations/webhook/{job_id}",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


def test_webhook_wrong_trigger_type(client: TestClient):
    """Jobs with trigger_type=manual should reject webhook calls."""
    job_id, _ = _create_manual_job(client, f"manual-wh-{uuid.uuid4().hex[:4]}")

    resp = client.post(f"/api/automations/webhook/{job_id}")
    assert resp.status_code == 400


def test_webhook_not_found(client: TestClient):
    resp = client.post(f"/api/automations/webhook/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/platforms/{id}/refresh-info
# ---------------------------------------------------------------------------

def test_refresh_platform_info_not_found(client: TestClient):
    resp = client.post(f"/api/platforms/{uuid.uuid4()}/refresh-info")
    assert resp.status_code == 404


def test_refresh_platform_info_unreachable(client: TestClient):
    """An unreachable platform should return 400 (SSH fails)."""
    p = client.post(
        "/api/platforms/",
        json={
            "name": "refresh-test-plat",
            "host": "10.255.255.1",  # unreachable
            "port": 22,
            "username": "ops",
            "auth_method": "password",
            "password": "s3cr3tXYZ",
        },
    )
    assert p.status_code == 201
    pid = p.json()["id"]

    with patch(
        "app.scheduler.collect_system_info",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = client.post(f"/api/platforms/{pid}/refresh-info")

    assert resp.status_code == 400


def test_refresh_platform_info_success(client: TestClient):
    """A reachable platform should return 200 with system_info."""
    p = client.post(
        "/api/platforms/",
        json={
            "name": "refresh-ok-plat",
            "host": "10.0.0.5",
            "port": 22,
            "username": "ops",
            "auth_method": "password",
            "password": "s3cr3tXYZ",
        },
    )
    assert p.status_code == 201
    pid = p.json()["id"]

    fake_info = {
        "hostname": "test-host",
        "kernel": "5.15.0",
        "uptime": "up 2 days",
        "cpu": "Intel Xeon (4 cores)",
        "memory": "8G total, 2G used, 6G free",
        "disk": "50G total, 10G used, 40G free, 20% used%",
        "load_average": "0.10 0.15 0.12",
        "refreshed_at": "2025-01-01T00:00:00",
    }

    with patch(
        "app.scheduler.collect_system_info",
        new_callable=AsyncMock,
        return_value=fake_info,
    ):
        resp = client.post(f"/api/platforms/{pid}/refresh-info")

    assert resp.status_code == 200
    data = resp.json()
    assert data["system_info"]["hostname"] == "test-host"
    assert data["system_info"]["kernel"] == "5.15.0"


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def test_notify_no_settings_is_noop():
    """notify_task_completion does nothing when automation_job_id is None."""
    import asyncio
    from app.notifications import notify_task_completion

    asyncio.run(
        notify_task_completion(
            task_run_id="fake-task",
            automation_job_id=None,
            platform_name="test-plat",
            platform_id="fake-pid",
            status="success",
        )
    )


def test_notify_webhook_sent(client: TestClient):
    """Completing a job with webhook settings triggers an outbound POST."""
    from unittest.mock import AsyncMock, patch, MagicMock
    import asyncio
    from app.notifications import notify_task_completion

    # Create a platform + automation job with webhook notification settings
    p = client.post(
        "/api/platforms/",
        json={
            "name": "notif-plat",
            "host": "10.9.9.1",
            "port": 22,
            "username": "ops",
            "auth_method": "password",
            "password": "s3cr3t",
        },
    )
    assert p.status_code == 201
    pid = p.json()["id"]

    j = client.post(
        "/api/automations/",
        json={
            "name": "notif-job",
            "execution_type": "command",
            "command": "echo hi",
            "trigger_type": "manual",
            "run_on_all_platforms": False,
            "target_platform_ids": [pid],
            "timeout_seconds": 30,
            "max_retries": 0,
            "retry_delay_seconds": 60,
            "is_enabled": True,
            "notification_settings": {
                "webhook": {"url": "https://hooks.example.com/test", "on": "always"}
            },
        },
    )
    assert j.status_code == 201
    job_id = j.json()["id"]

    posted_payloads = []

    class FakeResponse:
        status_code = 200

    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            pass
        async def post(self, url, **kwargs):
            posted_payloads.append({"url": url, **kwargs})
            return FakeResponse()

    with patch("app.notifications.httpx.AsyncClient", return_value=FakeClient()):
        asyncio.run(
            notify_task_completion(
                task_run_id="task-xyz",
                automation_job_id=job_id,
                platform_name="notif-plat",
                platform_id=pid,
                status="success",
                triggered_by="manual",
            )
        )

    assert len(posted_payloads) == 1
    assert posted_payloads[0]["url"] == "https://hooks.example.com/test"
    body = posted_payloads[0]["json"]
    assert body["status"] == "success"
    assert body["job_id"] == job_id


def test_notify_on_failure_only_skips_success(client: TestClient):
    """Webhook with on=failure should not fire for successful tasks."""
    from unittest.mock import patch
    import asyncio
    from app.notifications import notify_task_completion

    p = client.post(
        "/api/platforms/",
        json={
            "name": "notif-skip-plat",
            "host": "10.9.9.2",
            "port": 22,
            "username": "ops",
            "auth_method": "password",
            "password": "s3cr3t",
        },
    )
    pid = p.json()["id"]

    j = client.post(
        "/api/automations/",
        json={
            "name": "notif-skip-job",
            "execution_type": "command",
            "command": "echo hi",
            "trigger_type": "manual",
            "run_on_all_platforms": False,
            "target_platform_ids": [pid],
            "timeout_seconds": 30,
            "max_retries": 0,
            "retry_delay_seconds": 60,
            "is_enabled": True,
            "notification_settings": {
                "webhook": {"url": "https://hooks.example.com/fail-only", "on": "failure"}
            },
        },
    )
    job_id = j.json()["id"]

    called = []

    with patch("app.notifications._send_webhook", side_effect=lambda *a, **kw: called.append(1)):
        asyncio.run(
            notify_task_completion(
                task_run_id="task-abc",
                automation_job_id=job_id,
                platform_name="notif-skip-plat",
                platform_id=pid,
                status="success",   # should NOT trigger on=failure webhook
            )
        )

    assert called == [], "Webhook should not fire for success when on=failure"
