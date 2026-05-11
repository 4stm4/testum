# SPDX-License-Identifier: MIT
"""CRON scheduler for AutomationJob and periodic platform system_info refresh.

Two background loops run alongside the PyJobKit worker:
  • run_scheduler()         — fires due CRON automation jobs every minute
  • run_system_info_refresher() — refreshes Platform.system_info every hour
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from croniter import croniter

import app.db as _app_db
from app.models import (
    AutomationExecutionEnum,
    AutomationJob,
    AutomationTriggerEnum,
    Platform,
    Script,
    TaskRun,
    TaskStatusEnum,
    TaskTypeEnum,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL = 60          # seconds between CRON scheduler ticks
SYSTEM_INFO_INTERVAL = 3600  # seconds between platform system_info refreshes


def calc_next_run(cron_expr: str, base: datetime | None = None) -> datetime:
    """Return the next UTC datetime after *base* for the given cron expression."""
    base = base or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return croniter(cron_expr, base).get_next(datetime).replace(tzinfo=timezone.utc)


def _resolve_command(job: AutomationJob, db) -> str | None:
    """Return the shell command to run for this job."""
    if job.execution_type == AutomationExecutionEnum.COMMAND or job.execution_type == "command":
        return job.command
    # SCRIPT — load content from scripts table
    if job.script_id:
        script: Script | None = db.query(Script).filter(Script.id == job.script_id).first()
        if script:
            return script.content
    return None


def _get_target_platforms(job: AutomationJob, db) -> list[Platform]:
    """Return the list of Platform objects this job should run on."""
    if job.run_on_all_platforms:
        return db.query(Platform).all()
    return [link.platform for link in job.platform_links if link.platform]


async def dispatch_automation_job(job_id: str, triggered_by: str = "cron") -> list[str]:
    """
    Enqueue run_command tasks for all target platforms of an automation job.

    Returns a list of pyjobkit job_id strings that were enqueued.
    """
    from app.task_engine import engine  # late import to avoid circular deps

    enqueued: list[str] = []

    with _app_db.SessionLocal() as db:
        job: AutomationJob | None = db.query(AutomationJob).filter(
            AutomationJob.id == job_id
        ).first()

        if not job or not job.is_enabled:
            logger.warning("Automation job %s not found or disabled, skipping", job_id)
            return enqueued

        command = _resolve_command(job, db)
        if not command:
            logger.error("Automation job %s has no command/script to execute", job_id)
            return enqueued

        platforms = _get_target_platforms(job, db)
        if not platforms:
            logger.warning("Automation job %s has no target platforms", job_id)
            return enqueued

        for platform in platforms:
            task_run = TaskRun(
                id=uuid.uuid4(),
                type=TaskTypeEnum.RUN_COMMAND,
                platform_id=platform.id,
                status=TaskStatusEnum.PENDING,
                task_metadata={
                    "command": command,
                    "timeout": job.timeout_seconds,
                    "automation_job_id": str(job.id),
                    "triggered_by": triggered_by,
                },
            )
            db.add(task_run)
            db.flush()

            pyjobkit_id = await engine.enqueue(
                kind="run_command",
                payload={
                    "task_run_id": str(task_run.id),
                    "platform_id": str(platform.id),
                    "command": command,
                    "timeout": job.timeout_seconds,
                },
                max_attempts=job.max_retries + 1,
                timeout_s=job.timeout_seconds,
            )
            task_run.pyjobkit_job_id = str(pyjobkit_id)
            enqueued.append(str(pyjobkit_id))
            logger.info(
                "Dispatched automation job %s → platform %s → pyjobkit %s",
                job_id, platform.name, pyjobkit_id,
            )

        # Update run timestamps
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        job.last_run_at = now
        if job.trigger_type in (AutomationTriggerEnum.CRON, "cron") and job.cron_expression:
            job.next_run_at = calc_next_run(job.cron_expression).replace(tzinfo=None)

        db.commit()

    return enqueued


async def _tick() -> None:
    """Run one scheduler tick: dispatch all due CRON jobs."""
    now = datetime.utcnow()
    with _app_db.SessionLocal() as db:
        due_jobs: list[AutomationJob] = (
            db.query(AutomationJob)
            .filter(
                AutomationJob.is_enabled == True,
                AutomationJob.trigger_type == AutomationTriggerEnum.CRON,
                AutomationJob.cron_expression != None,
                AutomationJob.next_run_at != None,
                AutomationJob.next_run_at <= now,
            )
            .all()
        )
        job_ids = [str(j.id) for j in due_jobs]

    for job_id in job_ids:
        try:
            await dispatch_automation_job(job_id, triggered_by="cron")
        except Exception:
            logger.exception("Error dispatching automation job %s", job_id)


async def run_scheduler() -> None:
    """Main scheduler loop. Run this as an asyncio task alongside the worker."""
    logger.info("[scheduler] Starting CRON scheduler (poll interval: %ds)", POLL_INTERVAL)
    while True:
        try:
            await _tick()
        except Exception:
            logger.exception("[scheduler] Unexpected error in tick")
        await asyncio.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Platform system_info refresh
# ---------------------------------------------------------------------------

async def collect_system_info(platform: Platform) -> dict[str, Any] | None:
    """
    Connect to *platform* via SSH and collect current system information.

    Returns a dict on success, None if the platform is unreachable or
    credentials are missing/invalid.
    """
    from app.crypto import crypto
    from adapters.ssh.client import AsyncSSHClient

    password: str | None = None
    private_key: str | None = None

    try:
        auth = str(platform.auth_method.value if hasattr(platform.auth_method, "value") else platform.auth_method)
        if auth == "password":
            if not platform.encrypted_password:
                return None
            password = crypto.decrypt_string(platform.encrypted_password)
        elif auth == "private_key":
            if platform.ssh_key_id:
                with _app_db.SessionLocal() as db:
                    from app.models import SSHKey
                    key = db.query(SSHKey).filter(SSHKey.id == platform.ssh_key_id).first()
                    if key and key.encrypted_private_key:
                        private_key = crypto.decrypt_string(key.encrypted_private_key)
            elif platform.encrypted_private_key:
                private_key = crypto.decrypt_string(platform.encrypted_private_key)

        if not password and not private_key:
            return None
    except Exception as exc:
        logger.warning("[refresh] Credential error for platform %s: %s", platform.name, exc)
        return None

    info: dict[str, Any] = {}
    try:
        async with AsyncSSHClient(
            host=platform.host,
            port=platform.port,
            username=platform.username,
            password=password,
            private_key=private_key,
            known_host_fingerprint=platform.known_host_fingerprint,
        ) as ssh:
            async def run(cmd: str) -> str:
                _, out, _ = await ssh.execute_command(cmd)
                return out.strip()

            info["hostname"]     = await run("hostname")
            info["os_release"]   = await run("cat /etc/os-release 2>/dev/null || echo 'Unknown'")
            info["kernel"]       = await run("uname -r")
            info["uptime"]       = await run("uptime -p 2>/dev/null || uptime")
            info["cpu"]          = await run(
                "lscpu | grep 'Model name' | cut -d':' -f2 | xargs"
            ) + " (" + await run("nproc") + " cores)"
            info["memory"]       = await run(
                "free -h | grep Mem | awk '{print $2\" total, \"$3\" used, \"$4\" free\"}'"
            )
            info["disk"]         = await run(
                "df -h / | tail -1 | awk '{print $2\" total, \"$3\" used, \"$4\" free, \"$5\" used%\"}'"
            )
            info["load_average"] = await run("cat /proc/loadavg | awk '{print $1\" \"$2\" \"$3}'")
            info["refreshed_at"] = datetime.utcnow().isoformat()

            fingerprint = ssh.get_host_fingerprint()
            if fingerprint:
                info["host_fingerprint"] = fingerprint

    except Exception as exc:
        logger.warning("[refresh] SSH error for platform %s (%s): %s", platform.name, platform.host, exc)
        return None

    return info


async def refresh_platform(platform_id: str) -> dict[str, Any] | None:
    """
    Refresh system_info for a single platform and persist it to the DB.

    Returns the collected info dict, or None if the platform was unreachable.
    """
    with _app_db.SessionLocal() as db:
        platform: Platform | None = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            return None

        info = await collect_system_info(platform)
        if info is not None:
            platform.system_info = info
            # Store fingerprint if we got a fresh one
            if "host_fingerprint" in info and not platform.known_host_fingerprint:
                platform.known_host_fingerprint = info["host_fingerprint"]
            db.commit()
            logger.info("[refresh] Updated system_info for platform %s", platform.name)

    return info


async def _refresh_all_platforms() -> None:
    """Refresh system_info for every platform in the DB concurrently."""
    with _app_db.SessionLocal() as db:
        platform_ids = [str(p.id) for p in db.query(Platform.id).all()]

    if not platform_ids:
        return

    logger.info("[refresh] Refreshing system_info for %d platform(s)", len(platform_ids))
    results = await asyncio.gather(
        *[refresh_platform(pid) for pid in platform_ids],
        return_exceptions=True,
    )
    ok = sum(1 for r in results if isinstance(r, dict))
    logger.info("[refresh] system_info refresh complete: %d/%d succeeded", ok, len(platform_ids))


async def run_system_info_refresher() -> None:
    """
    Periodic loop that refreshes Platform.system_info every hour.
    Run alongside run_scheduler() via asyncio.gather in the worker.
    """
    logger.info("[refresh] Starting system_info refresher (interval: %ds)", SYSTEM_INFO_INTERVAL)
    # Initial delay — let the worker settle before hammering SSH on startup
    await asyncio.sleep(30)
    while True:
        try:
            await _refresh_all_platforms()
        except Exception:
            logger.exception("[refresh] Unexpected error during platform refresh")
        await asyncio.sleep(SYSTEM_INFO_INTERVAL)
