# SPDX-License-Identifier: MIT
"""Email + outbound webhook notifier."""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any, Dict

import httpx

from core.interfaces.storage import Storage
from infrastructure.config import config

logger = logging.getLogger(__name__)


def _should_notify(on: str, status: str) -> bool:
    return on == "always" or on == status


def _send_email_sync(to: list, subject: str, body: str) -> None:
    if not config.SMTP_HOST:
        logger.warning("[notify] SMTP_HOST not configured — skipping email")
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = ", ".join(to)
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as smtp:
            if config.SMTP_TLS:
                smtp.starttls(context=ctx)
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD or "")
            smtp.sendmail(config.SMTP_FROM, to, msg.as_string())
        logger.info("[notify] Email sent to %s", to)
    except Exception as exc:
        logger.warning("[notify] Email failed: %s", exc)


async def _send_webhook(url: str, payload: Dict[str, Any], secret: str | None) -> None:
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Testum-Secret"] = secret
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=headers)
            logger.info("[notify] Webhook %s → %d", url, resp.status_code)
    except Exception as exc:
        logger.warning("[notify] Webhook failed: %s", exc)


class SmtpWebhookNotifier:
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    async def notify_task_completion(
        self,
        *,
        task_run_id: str,
        automation_job_id: str | None,
        platform_name: str,
        platform_id: str,
        status: str,
        triggered_by: str = "manual",
        stdout_snippet: str = "",
    ) -> None:
        if not automation_job_id:
            return
        try:
            job = self._storage.get_automation_by_id(automation_job_id)
            if not job:
                return
            settings: Dict[str, Any] = job.notification_settings or {}
        except Exception as exc:
            logger.warning("[notify] Could not load job %s: %s", automation_job_id, exc)
            return

        if not settings:
            return

        now = datetime.now(timezone.utc).isoformat()

        email_cfg = settings.get("email")
        if email_cfg and isinstance(email_cfg, dict):
            on = email_cfg.get("on", "always")
            to = email_cfg.get("to", [])
            if to and _should_notify(on, status):
                icon = "✓" if status == "success" else "✗"
                subject = f"[Testum] {icon} {job.name} — {status.upper()} on {platform_name}"
                body = (
                    f"Automation job: {job.name}\n"
                    f"Platform      : {platform_name}\n"
                    f"Status        : {status.upper()}\n"
                    f"Task run ID   : {task_run_id}\n"
                    f"Finished at   : {now}\n"
                )
                if stdout_snippet:
                    body += f"\n--- Output ---\n{stdout_snippet[-2000:]}\n"
                await asyncio.to_thread(_send_email_sync, to, subject, body)

        webhook_cfg = settings.get("webhook")
        if webhook_cfg and isinstance(webhook_cfg, dict):
            url = webhook_cfg.get("url")
            on = webhook_cfg.get("on", "always")
            secret = webhook_cfg.get("secret")
            if url and _should_notify(on, status):
                payload = {
                    "event": "task_completed",
                    "status": status,
                    "job_id": str(job.id),
                    "job_name": job.name,
                    "task_run_id": task_run_id,
                    "platform_id": platform_id,
                    "platform_name": platform_name,
                    "triggered_by": triggered_by,
                    "finished_at": now,
                }
                await _send_webhook(url, payload, secret)
