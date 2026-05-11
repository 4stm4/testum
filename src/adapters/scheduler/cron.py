# SPDX-License-Identifier: MIT
"""CRON scheduler and platform system-info refresher."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from croniter import croniter

from core.domain.enums import TaskStatus, TaskType
from core.interfaces.storage import Storage

logger = logging.getLogger(__name__)

POLL_INTERVAL = 60
SYSTEM_INFO_INTERVAL = 3600


def calc_next_run(cron_expr: str, base: Optional[datetime] = None) -> datetime:
    base = base or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return croniter(cron_expr, base).get_next(datetime).replace(tzinfo=timezone.utc)


class CronScheduler:
    def __init__(self, storage: Storage, engine) -> None:
        self._storage = storage
        self._engine = engine

    async def tick(self) -> None:
        now = datetime.utcnow()
        jobs = self._storage.list_automations(limit=500)
        due = [
            j for j in jobs
            if j.is_enabled
            and j.trigger_type.value == "cron"
            and j.cron_expression
            and j.next_run_at is not None
            and j.next_run_at <= now
        ]
        for job in due:
            try:
                await self._dispatch(job)
            except Exception:
                logger.exception("Error dispatching automation job %s", job.id)

    async def _dispatch(self, job) -> None:
        command: Optional[str] = None
        if job.execution_type.value == "command":
            command = job.command
        elif job.script_id:
            script = self._storage.get_script_by_id(job.script_id)
            if script:
                command = script.content

        if not command:
            logger.error("Automation job %s has no command/script", job.id)
            return

        if job.run_on_all_platforms:
            platforms = self._storage.list_platforms(limit=500)
        else:
            platforms = [self._storage.get_platform_by_id(pid) for pid in job.platform_ids]
            platforms = [p for p in platforms if p]

        if not platforms:
            logger.warning("Automation job %s has no target platforms", job.id)
            return

        for platform in platforms:
            task_run = self._storage.create_task_run(
                id=uuid.uuid4(),
                type=TaskType.RUN_COMMAND,
                platform_id=platform.id,
                status=TaskStatus.PENDING,
                task_metadata={
                    "command": command,
                    "timeout": job.timeout_seconds,
                    "automation_job_id": str(job.id),
                    "triggered_by": "cron",
                },
            )
            pyjobkit_id = await self._engine.enqueue(
                kind="run_command",
                payload={
                    "task_run_id": str(task_run.id),
                    "platform_id": str(platform.id),
                    "command": command,
                    "timeout": job.timeout_seconds,
                    "automation_job_id": str(job.id),
                    "triggered_by": "cron",
                },
                max_attempts=job.max_retries + 1,
            )
            self._storage.update_task_run(str(task_run.id), pyjobkit_job_id=str(pyjobkit_id))
            logger.info("Dispatched job %s → platform %s → %s", job.id, platform.name, pyjobkit_id)

        now_naive = datetime.utcnow()
        updates: dict = {"last_run_at": now_naive}
        if job.cron_expression:
            updates["next_run_at"] = calc_next_run(job.cron_expression).replace(tzinfo=None)
        self._storage.update_automation(str(job.id), **updates)

    async def run(self) -> None:
        logger.info("[scheduler] Starting CRON scheduler (poll: %ds)", POLL_INTERVAL)
        while True:
            try:
                await self.tick()
            except Exception:
                logger.exception("[scheduler] Unexpected error in tick")
            await asyncio.sleep(POLL_INTERVAL)


# ── System info refresher ──────────────────────────────────────────────────

async def _collect_system_info(
    platform,
    storage: Storage,
) -> Optional[dict]:
    from adapters.ssh.asyncssh_client import AsyncSSHClient
    from adapters.postgres.session import SessionLocal
    from adapters.postgres.orm_models import PlatformRow, SSHKeyRow
    from infrastructure.crypto import crypto

    password: Optional[str] = None
    private_key: Optional[str] = None

    try:
        with SessionLocal() as db:
            row = db.query(PlatformRow).filter(PlatformRow.id == platform.id).first()
            if not row:
                return None
            auth = row.auth_method.value if hasattr(row.auth_method, "value") else row.auth_method
            if auth == "password" and row.encrypted_password:
                password = crypto.decrypt_string(row.encrypted_password)
            elif auth == "private_key":
                if row.ssh_key_id:
                    k = db.query(SSHKeyRow).filter(SSHKeyRow.id == row.ssh_key_id).first()
                    if k and k.encrypted_private_key:
                        private_key = crypto.decrypt_string(k.encrypted_private_key)
                elif row.encrypted_private_key:
                    private_key = crypto.decrypt_string(row.encrypted_private_key)
    except Exception as exc:
        logger.warning("[refresh] Credential error for %s: %s", platform.name, exc)
        return None

    if not password and not private_key:
        return None

    ssh = AsyncSSHClient(
        host=platform.host, port=platform.port,
        username=platform.username, password=password, private_key=private_key,
    )
    info: dict[str, Any] = {}
    try:
        ok, err = await asyncio.wait_for(ssh.connect(), timeout=15)
        if not ok:
            return None

        async def run(cmd: str) -> str:
            _, out, _ = await ssh.execute_command(cmd)
            return out.strip()

        info["hostname"] = await run("hostname")
        info["kernel"] = await run("uname -r")
        info["uptime"] = await run("uptime -p 2>/dev/null || uptime")
        info["cpu"] = (
            await run("lscpu | grep 'Model name' | cut -d':' -f2 | xargs")
            + " (" + await run("nproc") + " cores)"
        )
        info["memory"] = await run(
            "free -h | grep Mem | awk '{print $2\" total, \"$3\" used, \"$4\" free\"}'"
        )
        info["disk"] = await run(
            "df -h / | tail -1 | awk '{print $2\" total, \"$3\" used, \"$4\" free, \"$5\" used%\"}'"
        )
        info["load_average"] = await run("cat /proc/loadavg | awk '{print $1\" \"$2\" \"$3}'")
        info["refreshed_at"] = datetime.utcnow().isoformat()
    except Exception as exc:
        logger.warning("[refresh] SSH error for %s: %s", platform.name, exc)
        return None
    finally:
        await ssh.close()

    return info


class SystemInfoRefresher:
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    async def refresh_all(self) -> None:
        platforms = self._storage.list_platforms(limit=500)
        if not platforms:
            return
        logger.info("[refresh] Refreshing system_info for %d platform(s)", len(platforms))
        results = await asyncio.gather(
            *[self._refresh_one(p) for p in platforms],
            return_exceptions=True,
        )
        ok = sum(1 for r in results if isinstance(r, dict))
        logger.info("[refresh] Done: %d/%d succeeded", ok, len(platforms))

    async def _refresh_one(self, platform) -> Optional[dict]:
        info = await _collect_system_info(platform, self._storage)
        if info is not None:
            self._storage.update_platform(str(platform.id), system_info=info)
            logger.info("[refresh] Updated system_info for %s", platform.name)
        return info

    async def run(self) -> None:
        logger.info("[refresh] Starting system_info refresher (interval: %ds)", SYSTEM_INFO_INTERVAL)
        await asyncio.sleep(30)
        while True:
            try:
                await self.refresh_all()
            except Exception:
                logger.exception("[refresh] Unexpected error")
            await asyncio.sleep(SYSTEM_INFO_INTERVAL)
