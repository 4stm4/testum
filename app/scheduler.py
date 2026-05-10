# SPDX-License-Identifier: MIT
"""CRON scheduler for AutomationJob.

Runs as a background asyncio task alongside the PyJobKit worker.
Every minute it queries automation_jobs for enabled CRON jobs whose
next_run_at is in the past, dispatches them via the PyJobKit engine,
and updates last_run_at / next_run_at.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from croniter import croniter

from app.db import SessionLocal
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

POLL_INTERVAL = 60  # seconds between scheduler ticks


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

    with SessionLocal() as db:
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
    with SessionLocal() as db:
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
