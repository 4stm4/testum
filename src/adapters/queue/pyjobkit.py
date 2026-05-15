# SPDX-License-Identifier: MIT
"""PyJobKit executors and JobQueue adapter."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from pyjobkit.contracts import ExecContext, Executor

from adapters.ssh.client import AsyncSSHClient
from adapters.storage.minio import MinioArtifactStore
from core.domain.enums import TaskStatus
from core.interfaces.notifier import Notifier
from core.interfaces.storage import Storage

logger = logging.getLogger(__name__)


# ── Shared helpers ─────────────────────────────────────────────────────────

def _load_platform_creds(storage: Storage, platform_id: str) -> dict:
    """Return SSH connection kwargs by decrypting platform credentials."""
    from adapters.postgres.session import SessionLocal
    from adapters.postgres.orm_models import PlatformRow, SSHKeyRow
    from app.crypto import crypto

    with SessionLocal() as db:
        row = db.query(PlatformRow).filter(PlatformRow.id == platform_id).first()
        if not row:
            raise ValueError(f"Platform {platform_id} not found")

        auth = row.auth_method.value if hasattr(row.auth_method, "value") else row.auth_method
        password: Optional[str] = None
        private_key: Optional[str] = None

        if auth == "password":
            if not row.encrypted_password:
                raise ValueError("Platform has no password configured")
            password = crypto.decrypt_string(row.encrypted_password)
        elif auth == "private_key":
            if row.ssh_key_id:
                key_row = db.query(SSHKeyRow).filter(SSHKeyRow.id == row.ssh_key_id).first()
                if not key_row or not key_row.encrypted_private_key:
                    raise ValueError("SSH key not found or has no private key")
                private_key = crypto.decrypt_string(key_row.encrypted_private_key)
            elif row.encrypted_private_key:
                private_key = crypto.decrypt_string(row.encrypted_private_key)
            else:
                raise ValueError("Platform has no SSH key configured")

        return dict(
            host=row.host,
            port=row.port,
            username=row.username,
            password=password,
            private_key=private_key,
            name=row.name,
        )


def _update_status(storage: Storage, task_run_id: str, status: TaskStatus, **kw: Any) -> None:
    storage.update_task_run(task_run_id, status=status, **kw)


# ── DeployKeysExecutor ─────────────────────────────────────────────────────

class DeployKeysExecutor(Executor):
    kind = "deploy_keys"

    def __init__(self, storage: Storage, artifact_store: MinioArtifactStore) -> None:
        self._storage = storage
        self._artifacts = artifact_store

    async def run(self, *, job_id: str, payload: Dict[str, Any], ctx: ExecContext) -> dict:
        logger.info("[DeployKeysExecutor] START job_id=%s", job_id)
        task_run_id = payload["task_run_id"]
        platform_id = payload["platform_id"]
        key_ids = payload.get("key_ids")

        await asyncio.to_thread(
            _update_status, self._storage, task_run_id, TaskStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        await ctx.set_progress(0.0)
        await ctx.log("Starting key deployment...")

        async with ctx.profile_phase("load-credentials"):
            creds = await asyncio.to_thread(_load_platform_creds, self._storage, platform_id)
        await ctx.set_progress(0.2)
        await ctx.log(f"Connecting to {creds['name']}...")

        keys = self._storage.list_keys(limit=200) if not key_ids else [
            self._storage.get_key_by_id(kid) for kid in key_ids
        ]
        keys = [k for k in keys if k]
        if not keys:
            raise ValueError("No SSH keys found to deploy")
        await ctx.log(f"Found {len(keys)} keys to deploy")

        try:
            async with ctx.profile_phase("ssh-connect", host=creds["host"]):
                ssh_client = AsyncSSHClient(
                    host=creds["host"], port=creds["port"],
                    username=creds["username"], password=creds["password"],
                    private_key=creds["private_key"],
                )

            async with ssh_client as ssh:
                await ctx.set_progress(0.4)
                await ctx.log("Connected to platform")
                deployed = 0
                lines = []

                async with ctx.profile_phase("deploy-keys", key_count=len(keys)):
                    for key in keys:
                        if await ctx.is_cancelled():
                            raise RuntimeError("Task cancelled by user")
                        await ctx.log(f"Deploying key: {key.name}")
                        cmd = (
                            "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
                            f'echo "{key.public_key}" >> ~/.ssh/authorized_keys && '
                            "chmod 600 ~/.ssh/authorized_keys"
                        )
                        code, stdout, stderr = await ssh.execute_command(cmd)
                        if stderr:
                            lines.append(f"[{key.name}] stderr: {stderr}")
                            await ctx.log(f"[{key.name}] {stderr}")
                        if code != 0:
                            msg = f"[{key.name}] failed (exit {code}): {stderr or stdout}"
                            lines.append(msg)
                            await ctx.log(msg)
                            continue
                        lines.append(f"[{key.name}] Deployed successfully")
                        await ctx.log(f"[{key.name}] Deployed successfully")
                        deployed += 1

                await ctx.set_progress(0.8)
                s3_key = f"tasks/{task_run_id}/output.txt"
                try:
                    self._artifacts.upload(s3_key, "\n".join(lines))
                except Exception as e:
                    logger.warning("[DeployKeysExecutor] S3 skipped: %s", e)
                    s3_key = None

                summary = f"Deployed {deployed}/{len(keys)} keys successfully"
                await ctx.log(summary)
                await asyncio.to_thread(
                    _update_status, self._storage, task_run_id, TaskStatus.SUCCESS,
                    finished_at=datetime.utcnow(), result_location=s3_key,
                )
                await ctx.set_progress(1.0)
                return {"task_id": str(job_id), "status": "success"}
        except Exception as exc:
            logger.exception("DeployKeysExecutor failed: %s", exc)
            await asyncio.to_thread(
                _update_status, self._storage, task_run_id, TaskStatus.FAILED,
                finished_at=datetime.utcnow(), error_message=str(exc),
            )
            await ctx.log(f"ERROR: {exc}")
            raise


# ── RunCommandExecutor ─────────────────────────────────────────────────────

class RunCommandExecutor(Executor):
    kind = "run_command"

    def __init__(
        self,
        storage: Storage,
        artifact_store: MinioArtifactStore,
        notifier: Notifier,
    ) -> None:
        self._storage = storage
        self._artifacts = artifact_store
        self._notifier = notifier

    async def run(self, *, job_id: str, payload: Dict[str, Any], ctx: ExecContext) -> dict:
        logger.info("[RunCommandExecutor] START job_id=%s", job_id)
        task_run_id = payload["task_run_id"]
        platform_id = payload["platform_id"]
        command = payload["command"]
        timeout: int = payload.get("timeout") or 60
        automation_job_id: Optional[str] = payload.get("automation_job_id")
        triggered_by: str = payload.get("triggered_by", "manual")
        platform_name = str(platform_id)

        await asyncio.to_thread(
            _update_status, self._storage, task_run_id, TaskStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        await ctx.set_progress(0.0)
        await ctx.log("Starting command execution...")

        async with ctx.profile_phase("load-credentials"):
            creds = await asyncio.to_thread(_load_platform_creds, self._storage, platform_id)
        platform_name = creds["name"]
        await ctx.set_progress(0.2)
        await ctx.log(f"Connecting to {platform_name}...")

        try:
            async with ctx.profile_phase("ssh-connect", host=creds["host"]):
                ssh_client = AsyncSSHClient(
                    host=creds["host"], port=creds["port"],
                    username=creds["username"], password=creds["password"],
                    private_key=creds["private_key"],
                )

            async with ssh_client as ssh:
                await ctx.set_progress(0.4)
                if await ctx.is_cancelled():
                    raise RuntimeError("Task cancelled by user")

                await ctx.log("Connected, executing command...")
                await ctx.log(f"$ {command}")

                async with ctx.profile_phase("ssh-exec", command=command[:80]):
                    code, stdout, stderr = await ssh.execute_command(command, timeout=timeout)

                if stdout:
                    await ctx.log(stdout)
                if stderr:
                    await ctx.log(f"[stderr] {stderr}")
                await ctx.log(f"\nExit code: {code}")

                await ctx.set_progress(0.8)
                content = (
                    f"Command: {command}\n\n=== EXIT CODE ===\n{code}\n\n"
                    f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}"
                )
                s3_key = f"tasks/{task_run_id}/output.txt"
                try:
                    self._artifacts.upload(s3_key, content)
                except Exception as e:
                    logger.warning("[RunCommandExecutor] S3 skipped: %s", e)
                    s3_key = None

                final_status = TaskStatus.SUCCESS if code == 0 else TaskStatus.FAILED
                await asyncio.to_thread(
                    _update_status, self._storage, task_run_id, final_status,
                    finished_at=datetime.utcnow(),
                    result_location=s3_key,
                    stderr=stderr or None,
                )

                await self._notifier.notify_task_completion(
                    task_run_id=task_run_id,
                    automation_job_id=automation_job_id,
                    platform_name=platform_name,
                    platform_id=str(platform_id),
                    status=final_status.value,
                    triggered_by=triggered_by,
                    stdout_snippet=stdout or "",
                )

                await ctx.set_progress(1.0)
                return {"task_id": str(job_id), "status": final_status.value}
        except Exception as exc:
            logger.exception("RunCommandExecutor failed: %s", exc)
            await asyncio.to_thread(
                _update_status, self._storage, task_run_id, TaskStatus.FAILED,
                finished_at=datetime.utcnow(), error_message=str(exc),
            )
            await self._notifier.notify_task_completion(
                task_run_id=task_run_id,
                automation_job_id=automation_job_id,
                platform_name=platform_name,
                platform_id=str(platform_id),
                status="failure",
                triggered_by=triggered_by,
            )
            await ctx.log(f"ERROR: {exc}")
            raise


# ── PyJobKit JobQueue adapter ──────────────────────────────────────────────

class PyJobKitQueue:
    """Thin async wrapper around a pyjobkit Engine."""

    def __init__(self, engine) -> None:
        self._engine = engine

    async def enqueue(self, kind: str, payload: Dict[str, Any], *, max_attempts: int = 1) -> str:
        job_id = await self._engine.enqueue(kind=kind, payload=payload, max_attempts=max_attempts)
        return str(job_id)

    async def cancel(self, job_id: str) -> bool:
        try:
            await self._engine.cancel(job_id)
            return True
        except Exception:
            return False
