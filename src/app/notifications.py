# SPDX-License-Identifier: MIT
"""Task completion notifications: email and outbound webhook.

notification_settings schema (stored as JSON on AutomationJob):
{
    "email": {
        "to": ["ops@example.com", "dev@example.com"],
        "on": "always"          // "success" | "failure" | "always"
    },
    "webhook": {
        "url": "https://hooks.example.com/notify",
        "on": "failure",        // "success" | "failure" | "always"
        "secret": "optional"    // added as X-Testum-Secret header
    }
}
Either key is optional. If both are absent, no notification is sent.
"""
from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any

import httpx

from app.config import config

logger = logging.getLogger(__name__)


def _should_notify(on: str, status: str) -> bool:
    if on == "always":
        return True
    return on == status


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def _send_email_sync(to: list[str], subject: str, body: str) -> None:
    if not config.SMTP_HOST:
        logger.warning("[notify] SMTP_HOST not configured — skipping email")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = ", ".join(to)

    context = ssl.create_default_context()
    try:
        if config.SMTP_TLS:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as smtp:
                smtp.starttls(context=context)
                if config.SMTP_USER:
                    smtp.login(config.SMTP_USER, config.SMTP_PASSWORD or "")
                smtp.sendmail(config.SMTP_FROM, to, msg.as_string())
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as smtp:
                if config.SMTP_USER:
                    smtp.login(config.SMTP_USER, config.SMTP_PASSWORD or "")
                smtp.sendmail(config.SMTP_FROM, to, msg.as_string())
        logger.info("[notify] Email sent to %s", to)
    except Exception as exc:
        logger.warning("[notify] Failed to send email: %s", exc)


def _build_email_body(
    job_name: str,
    platform_name: str,
    status: str,
    task_run_id: str,
    stdout_snippet: str,
) -> tuple[str, str]:
    icon = "✓" if status == "success" else "✗"
    subject = f"[Testum] {icon} {job_name} — {status.upper()} on {platform_name}"
    body = (
        f"Automation job: {job_name}\n"
        f"Platform      : {platform_name}\n"
        f"Status        : {status.upper()}\n"
        f"Task run ID   : {task_run_id}\n"
        f"Finished at   : {datetime.now(timezone.utc).isoformat()}\n"
    )
    if stdout_snippet:
        body += f"\n--- Output (last 2000 chars) ---\n{stdout_snippet[-2000:]}\n"
    return subject, body


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

async def _send_webhook(
    url: str,
    payload: dict[str, Any],
    secret: str | None = None,
) -> None:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if secret:
        headers["X-Testum-Secret"] = secret

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.warning(
                    "[notify] Webhook %s returned HTTP %d", url, resp.status_code
                )
            else:
                logger.info("[notify] Webhook delivered to %s (%d)", url, resp.status_code)
    except Exception as exc:
        logger.warning("[notify] Webhook to %s failed: %s", url, exc)


def _build_webhook_payload(
    job_id: str,
    job_name: str,
    platform_id: str,
    platform_name: str,
    task_run_id: str,
    status: str,
    triggered_by: str,
) -> dict[str, Any]:
    return {
        "event": "task_completed",
        "status": status,
        "job_id": job_id,
        "job_name": job_name,
        "task_run_id": task_run_id,
        "platform_id": platform_id,
        "platform_name": platform_name,
        "triggered_by": triggered_by,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def notify_task_completion(
    task_run_id: str,
    automation_job_id: str | None,
    platform_name: str,
    platform_id: str,
    status: str,
    triggered_by: str = "manual",
    stdout_snippet: str = "",
) -> None:
    """Send notifications for a completed task if the automation job has
    notification_settings configured.

    Called from executors after final status is written to the DB.
    Errors are swallowed so a notification failure never breaks the task.
    """
    if not automation_job_id:
        return

    try:
        import app.db as _db_module
        from app.models import AutomationJob

        with _db_module.SessionLocal() as db:
            job = db.query(AutomationJob).filter(
                AutomationJob.id == automation_job_id
            ).first()
            if not job:
                return
            settings: dict[str, Any] = job.notification_settings or {}
            job_name = job.name
            job_id_str = str(job.id)
    except Exception as exc:
        logger.warning("[notify] Could not load job %s: %s", automation_job_id, exc)
        return

    if not settings:
        return

    # --- email ---
    email_cfg = settings.get("email")
    if email_cfg and isinstance(email_cfg, dict):
        on = email_cfg.get("on", "always")
        to = email_cfg.get("to", [])
        if to and _should_notify(on, status):
            subject, body = _build_email_body(
                job_name=job_name,
                platform_name=platform_name,
                status=status,
                task_run_id=task_run_id,
                stdout_snippet=stdout_snippet,
            )
            await asyncio.to_thread(_send_email_sync, to, subject, body)

    # --- webhook ---
    webhook_cfg = settings.get("webhook")
    if webhook_cfg and isinstance(webhook_cfg, dict):
        url = webhook_cfg.get("url")
        on = webhook_cfg.get("on", "always")
        secret = webhook_cfg.get("secret")
        if url and _should_notify(on, status):
            payload = _build_webhook_payload(
                job_id=job_id_str,
                job_name=job_name,
                platform_id=platform_id,
                platform_name=platform_name,
                task_run_id=task_run_id,
                status=status,
                triggered_by=triggered_by,
            )
            await _send_webhook(url, payload, secret)
