import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

import boto3
from botocore.client import Config

from app.config import config
from app.crypto import crypto
from app.db import SessionLocal
from app.models import Platform, SSHKey, TaskRun, TaskStatusEnum
from app.ssh_helper import AsyncSSHClient
from pyjobkit.contracts import ExecContext, Executor

logger = logging.getLogger(__name__)


@dataclass
class PlatformInfo:
    id: int
    name: str
    host: str
    port: int
    username: str
    auth_method: str
    password: Optional[str]
    private_key_data: Optional[str]


@dataclass
class SSHKeyInfo:
    id: int
    name: str
    public_key: str


def _load_platform(platform_id: int) -> PlatformInfo:
    with SessionLocal() as db:
        platform = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            raise ValueError(f"Platform {platform_id} not found")

        password: Optional[str] = None
        private_key_data: Optional[str] = None

        if platform.auth_method == "password":
            if not platform.encrypted_password:
                raise ValueError("Platform has no password configured")
            password = crypto.decrypt_string(platform.encrypted_password)
        elif platform.auth_method == "private_key":
            if platform.ssh_key_id:
                key = db.query(SSHKey).filter(SSHKey.id == platform.ssh_key_id).first()
                if not key or not key.encrypted_private_key:
                    raise ValueError("SSH key not found or has no private key")
                private_key_data = crypto.decrypt_string(key.encrypted_private_key)
            elif platform.encrypted_private_key:
                private_key_data = crypto.decrypt_string(platform.encrypted_private_key)
            else:
                raise ValueError("Platform has no SSH key configured")

        return PlatformInfo(
            id=platform.id,
            name=platform.name,
            host=platform.host,
            port=platform.port,
            username=platform.username,
            auth_method=str(platform.auth_method.value if hasattr(platform.auth_method, "value") else platform.auth_method),
            password=password,
            private_key_data=private_key_data,
        )


def _load_keys(key_ids: Optional[Iterable[int]] = None) -> List[SSHKeyInfo]:
    with SessionLocal() as db:
        query = db.query(SSHKey)
        if key_ids:
            query = query.filter(SSHKey.id.in_(key_ids))
        keys = query.all()
        return [
            SSHKeyInfo(id=key.id, name=key.name, public_key=key.public_key)
            for key in keys
        ]


def _update_task_status(task_run_id: str, status: TaskStatusEnum, **updates) -> None:
    with SessionLocal() as db:
        task_run = db.query(TaskRun).filter(TaskRun.id == task_run_id).first()
        if not task_run:
            raise ValueError(f"TaskRun {task_run_id} not found")
        task_run.status = status
        for key, value in updates.items():
            setattr(task_run, key, value)
        db.commit()


def _append_task_stdout(task_run_id: str, text: str) -> None:
    """Append a line to TaskRun.stdout so the WebSocket can stream it incrementally."""
    with SessionLocal() as db:
        task_run = db.query(TaskRun).filter(TaskRun.id == task_run_id).first()
        if not task_run:
            return
        task_run.stdout = (task_run.stdout or "") + text + "\n"
        db.commit()

# Executor для деплоя ключей
class DeployKeysExecutor(Executor):
    kind = "deploy_keys"

    async def run(self, *, job_id, payload, ctx: ExecContext):
        logger.info(f"[DeployKeysExecutor] START run: job_id={job_id}, payload={payload}")
        task_run_id = payload["task_run_id"]
        platform_id = payload["platform_id"]
        key_ids = payload.get("key_ids")

        async def emit(text: str) -> None:
            await ctx.log(text)
            await asyncio.to_thread(_append_task_stdout, task_run_id, text)

        await asyncio.to_thread(
            _update_task_status,
            task_run_id,
            TaskStatusEnum.RUNNING,
            started_at=datetime.utcnow(),
        )

        logger.info(f"[DeployKeysExecutor] Status set to RUNNING for task_run_id={task_run_id}")
        await emit("Starting key deployment...")
        platform = await asyncio.to_thread(_load_platform, platform_id)
        logger.info(f"[DeployKeysExecutor] Platform loaded: {platform}")
        await emit(f"Connecting to {platform.name}...")
        keys = await asyncio.to_thread(_load_keys, key_ids)
        logger.info(f"[DeployKeysExecutor] Keys loaded: {keys}")
        if not keys:
            raise ValueError("No SSH keys found to deploy")

        await emit(f"Found {len(keys)} keys to deploy")

        ssh_client = AsyncSSHClient(
            host=platform.host,
            port=platform.port,
            username=platform.username,
            password=platform.password,
            private_key=platform.private_key_data,
        )

        try:
            logger.info(f"[DeployKeysExecutor] Connecting to SSH...")
            success, error = await ssh_client.connect()
            if not success:
                raise RuntimeError(error or "Failed to establish SSH connection")

            await emit("Connected to platform")
            deployed_count = 0
            output_lines: List[str] = []

            for key in keys:
                if await ctx.is_cancelled():
                    raise RuntimeError("Task cancelled by user")

                await emit(f"Deploying key: {key.name}")
                cmd = (
                    "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
                    f"echo \"{key.public_key}\" >> ~/.ssh/authorized_keys && "
                    "chmod 600 ~/.ssh/authorized_keys"
                )
                logger.info(f"[DeployKeysExecutor] Executing command for key {key.name}")
                exit_code, stdout, stderr = await ssh_client.execute_command(cmd)
                if stderr:
                    output_lines.append(f"[{key.name}] stderr: {stderr}")
                    await emit(f"[{key.name}] {stderr}")
                if exit_code != 0:
                    msg = f"[{key.name}] failed with code {exit_code}: {stderr or stdout}"
                    output_lines.append(msg)
                    await emit(msg)
                    continue
                output_lines.append(f"[{key.name}] Deployed successfully")
                await emit(f"[{key.name}] Deployed successfully")
                deployed_count += 1

            output_content = "\n".join(output_lines)
            s3_key = f"tasks/{task_run_id}/output.txt"
            logger.info(f"[DeployKeysExecutor] Uploading output to S3: {s3_key}")
            upload_to_s3(s3_key, output_content)

            summary = f"Deployed {deployed_count}/{len(keys)} keys successfully"
            await emit(summary)
            await asyncio.to_thread(
                _update_task_status,
                task_run_id,
                TaskStatusEnum.SUCCESS,
                finished_at=datetime.utcnow(),
                result_location=s3_key,
            )
            logger.info(f"[DeployKeysExecutor] Status set to SUCCESS for task_run_id={task_run_id}")
            logger.info(f"[DeployKeysExecutor] END run: job_id={job_id}, task_run_id={task_run_id}")
            return {"task_id": str(job_id), "status": "success"}
        except Exception as e:
            logger.exception(f"Task {task_run_id} failed")
            await asyncio.to_thread(
                _update_task_status,
                task_run_id,
                TaskStatusEnum.FAILED,
                finished_at=datetime.utcnow(),
                error_message=str(e),
            )
            logger.info(f"[DeployKeysExecutor] Status set to FAILED for task_run_id={task_run_id}")
            await emit(f"ERROR: {e}")
            raise
        finally:
            logger.info(f"[DeployKeysExecutor] Closing SSH client for task_run_id={task_run_id}")
            await ssh_client.close()

# Executor для запуска команды
class RunCommandExecutor(Executor):
    kind = "run_command"

    async def run(self, *, job_id, payload, ctx: ExecContext):
        logger.info(f"[RunCommandExecutor] START run: job_id={job_id}, payload={payload}")
        task_run_id = payload["task_run_id"]
        platform_id = payload["platform_id"]
        command = payload["command"]
        timeout: Optional[int] = payload.get("timeout")
        automation_job_id: Optional[str] = payload.get("automation_job_id")
        triggered_by: str = payload.get("triggered_by", "manual")
        _platform_name: str = str(platform_id)  # updated once platform is loaded

        async def emit(text: str, stream: str = "stdout") -> None:
            await ctx.log(text, stream=stream)
            await asyncio.to_thread(_append_task_stdout, task_run_id, text)

        await asyncio.to_thread(
            _update_task_status,
            task_run_id,
            TaskStatusEnum.RUNNING,
            started_at=datetime.utcnow(),
        )
        logger.info(f"[RunCommandExecutor] Status set to RUNNING for task_run_id={task_run_id}")

        await emit("Starting command execution...")
        platform = await asyncio.to_thread(_load_platform, platform_id)
        _platform_name = platform.name
        logger.info(f"[RunCommandExecutor] Platform loaded: {platform}")
        await emit(f"Connecting to {platform.name}...")

        ssh_client = AsyncSSHClient(
            host=platform.host,
            port=platform.port,
            username=platform.username,
            password=platform.password,
            private_key=platform.private_key_data,
        )

        try:
            logger.info(f"[RunCommandExecutor] Connecting to SSH...")
            success, error = await ssh_client.connect()
            if not success:
                raise RuntimeError(error or "Failed to establish SSH connection")

            if await ctx.is_cancelled():
                raise RuntimeError("Task cancelled by user")

            await emit("Connected, executing command...")
            await emit(f"$ {command}")
            logger.info(f"[RunCommandExecutor] Executing command: {command}")
            exit_code, stdout, stderr = await ssh_client.execute_command(
                command, timeout=timeout or 60
            )

            if stdout:
                await emit(stdout)
            if stderr:
                await emit(f"[stderr] {stderr}")

            await emit(f"\nExit code: {exit_code}")

            output_content = (
                f"Command: {command}\n\n=== EXIT CODE ===\n{exit_code}\n\n=== STDOUT ===\n"
                f"{stdout}\n\n=== STDERR ===\n{stderr}"
            )
            s3_key = f"tasks/{task_run_id}/output.txt"
            logger.info(f"[RunCommandExecutor] Uploading output to S3: {s3_key}")
            upload_to_s3(s3_key, output_content)

            final_status = TaskStatusEnum.SUCCESS if exit_code == 0 else TaskStatusEnum.FAILED
            await asyncio.to_thread(
                _update_task_status,
                task_run_id,
                final_status,
                finished_at=datetime.utcnow(),
                result_location=s3_key,
                stderr=stderr or None,
            )
            logger.info(f"[RunCommandExecutor] Status set to {final_status} for task_run_id={task_run_id}")

            from app.notifications import notify_task_completion
            await notify_task_completion(
                task_run_id=task_run_id,
                automation_job_id=automation_job_id,
                platform_name=_platform_name,
                platform_id=str(platform_id),
                status=final_status.value,
                triggered_by=triggered_by,
                stdout_snippet=stdout or "",
            )

            logger.info(f"[RunCommandExecutor] END run: job_id={job_id}, task_run_id={task_run_id}")
            return {"task_id": str(job_id), "status": final_status.value}
        except Exception as e:
            logger.exception(f"Task {task_run_id} failed")
            await asyncio.to_thread(
                _update_task_status,
                task_run_id,
                TaskStatusEnum.FAILED,
                finished_at=datetime.utcnow(),
                error_message=str(e),
            )
            logger.info(f"[RunCommandExecutor] Status set to FAILED for task_run_id={task_run_id}")

            from app.notifications import notify_task_completion
            await notify_task_completion(
                task_run_id=task_run_id,
                automation_job_id=automation_job_id,
                platform_name=_platform_name,
                platform_id=str(platform_id),
                status="failure",
                triggered_by=triggered_by,
            )

            await emit(f"ERROR: {e}")
            raise
        finally:
            logger.info(f"[RunCommandExecutor] Closing SSH client for task_run_id={task_run_id}")
            await ssh_client.close()



# MinIO/S3 client
s3_client = boto3.client(
    "s3",
    endpoint_url=f"http://{config.MINIO_ENDPOINT}" if not config.MINIO_SECURE else f"https://{config.MINIO_ENDPOINT}",
    aws_access_key_id=config.MINIO_ACCESS_KEY,
    aws_secret_access_key=config.MINIO_SECRET_KEY,
    config=Config(signature_version="s3v4"),
)


async def publish_task_message(task_id: str, msg_type: str, payload: str):
    """
    Log task message (WebSocket pub/sub removed - Redis not used).

    Args:
        task_id: Task ID
        msg_type: Message type (stdout, stderr, progress, done, error)
        payload: Message payload
    """
    logger.info(f"[{task_id}] {msg_type}: {payload}")


def ensure_s3_bucket():
    """Ensure MinIO bucket exists."""
    try:
        s3_client.head_bucket(Bucket=config.MINIO_BUCKET)
    except Exception:
        logger.info(f"Creating bucket: {config.MINIO_BUCKET}")
        s3_client.create_bucket(Bucket=config.MINIO_BUCKET)


def upload_to_s3(key: str, content: str) -> str:
    """
    Upload content to S3.

    Args:
        key: S3 object key
        content: Content to upload

    Returns:
        S3 key
    """
    ensure_s3_bucket()
    s3_client.put_object(
        Bucket=config.MINIO_BUCKET,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType="text/plain",
    )
    logger.info(f"Uploaded to S3: {key}")
    return key


