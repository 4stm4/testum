"""Celery tasks for SSH operations."""
import json
import logging
from datetime import datetime
from typing import List, Optional
from celery import Task
import redis
import boto3
from botocore.client import Config

from app.celery_app import celery_app
from app.config import config
from app.db import SessionLocal
from app.models import Platform, SSHKey, TaskRun, TaskStatusEnum
from app.crypto import crypto
from app.ssh_helper import SSHHelper

logger = logging.getLogger(__name__)

# Redis client for pub/sub
redis_client = redis.from_url(config.REDIS_URL)

# MinIO/S3 client
s3_client = boto3.client(
    "s3",
    endpoint_url=f"http://{config.MINIO_ENDPOINT}" if not config.MINIO_SECURE else f"https://{config.MINIO_ENDPOINT}",
    aws_access_key_id=config.MINIO_ACCESS_KEY,
    aws_secret_access_key=config.MINIO_SECRET_KEY,
    config=Config(signature_version="s3v4"),
)


def publish_task_message(task_id: str, msg_type: str, payload: str):
    """
    Publish message to Redis channel for WebSocket streaming.

    Args:
        task_id: Celery task ID
        msg_type: Message type (stdout, stderr, progress, done, error)
        payload: Message payload
    """
    message = {
        "ts": datetime.utcnow().isoformat(),
        "type": msg_type,
        "payload": payload,
    }
    channel = f"task:{task_id}"
    redis_client.publish(channel, json.dumps(message))
    logger.debug(f"Published to {channel}: {msg_type}")


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


class DatabaseTask(Task):
    """Base task with database session management."""

    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
)
def deploy_keys_task(self, task_run_id: str, platform_id: str, key_ids: Optional[List[str]] = None):
    """
    Deploy SSH keys to platform.

    Args:
        task_run_id: TaskRun ID
        platform_id: Platform ID
        key_ids: List of SSH key IDs to deploy (None = all keys)
    """
    db = self.db
    task_id = self.request.id

    try:
        # Update task status
        task_run = db.query(TaskRun).filter(TaskRun.id == task_run_id).first()
        if not task_run:
            raise ValueError(f"TaskRun {task_run_id} not found")

        task_run.status = TaskStatusEnum.RUNNING
        task_run.started_at = datetime.utcnow()
        db.commit()

        publish_task_message(task_id, "progress", "Starting key deployment...")

        # Get platform
        platform = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            raise ValueError(f"Platform {platform_id} not found")

        publish_task_message(task_id, "progress", f"Connecting to {platform.name} ({platform.host})...")

        # Decrypt credentials
        password = None
        private_key = None
        if platform.auth_method.value == "password" and platform.encrypted_password:
            password = crypto.decrypt_string(platform.encrypted_password)
        elif platform.auth_method.value == "private_key":
            # Get private key from SSHKey reference
            if platform.ssh_key_id:
                ssh_key = db.query(SSHKey).filter(SSHKey.id == platform.ssh_key_id).first()
                if ssh_key and ssh_key.encrypted_private_key:
                    private_key = crypto.decrypt_string(ssh_key.encrypted_private_key)
            elif platform.encrypted_private_key:
                # Legacy: use encrypted_private_key directly
                private_key = crypto.decrypt_string(platform.encrypted_private_key)

        # Get keys to deploy
        if key_ids:
            keys = db.query(SSHKey).filter(SSHKey.id.in_(key_ids)).all()
        else:
            keys = db.query(SSHKey).all()

        if not keys:
            raise ValueError("No keys found to deploy")

        publish_task_message(task_id, "progress", f"Found {len(keys)} key(s) to deploy")

        # Connect via SSH
        ssh = SSHHelper(
            host=platform.host,
            port=platform.port,
            username=platform.username,
            password=password,
            private_key=private_key,
            known_host_fingerprint=platform.known_host_fingerprint,
        )

        success, error_msg = ssh.connect()
        if not success:
            raise Exception(f"SSH connection failed: {error_msg}")

        # Save host fingerprint if not set
        if not platform.known_host_fingerprint:
            fingerprint = ssh.get_host_fingerprint()
            if fingerprint:
                platform.known_host_fingerprint = fingerprint
                db.commit()
                publish_task_message(task_id, "progress", f"Saved host fingerprint: {fingerprint[:16]}...")

        publish_task_message(task_id, "progress", "Connected successfully. Deploying keys...")

        # Deploy keys
        public_keys = [key.public_key for key in keys]
        success, message = ssh.deploy_authorized_keys(public_keys)

        if not success:
            raise Exception(f"Key deployment failed: {message}")

        publish_task_message(task_id, "progress", message)

        # Upload authorized_keys snapshot to S3
        auth_keys_content = ssh.read_file(f"/home/{platform.username}/.ssh/authorized_keys") or ""
        s3_key = f"platforms/{platform_id}/authorized_keys_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        upload_to_s3(s3_key, auth_keys_content)

        ssh.close()

        # Update task status
        task_run.status = TaskStatusEnum.SUCCESS
        task_run.finished_at = datetime.utcnow()
        task_run.result_location = s3_key
        task_run.stdout = message
        db.commit()

        publish_task_message(task_id, "done", f"Deployment completed successfully. {message}")
        logger.info(f"Task {task_id} completed successfully")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Task {task_id} failed: {error_msg}")

        # Update task status
        task_run = db.query(TaskRun).filter(TaskRun.id == task_run_id).first()
        if task_run:
            task_run.status = TaskStatusEnum.FAILED
            task_run.finished_at = datetime.utcnow()
            task_run.error_message = error_msg
            db.commit()

        publish_task_message(task_id, "error", f"Deployment failed: {error_msg}")
        raise


@celery_app.task(
    bind=True,
    base=DatabaseTask,
)
def run_command_task(self, task_run_id: str, platform_id: str, command: str, timeout: int = 60):
    """
    Run command on platform.

    Args:
        task_run_id: TaskRun ID
        platform_id: Platform ID
        command: Command to execute
        timeout: Command timeout in seconds
    """
    db = self.db
    task_id = self.request.id

    try:
        # Update task status
        task_run = db.query(TaskRun).filter(TaskRun.id == task_run_id).first()
        if not task_run:
            raise ValueError(f"TaskRun {task_run_id} not found")

        task_run.status = TaskStatusEnum.RUNNING
        task_run.started_at = datetime.utcnow()
        db.commit()

        publish_task_message(task_id, "progress", f"Executing command: {command}")

        # Get platform
        platform = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            raise ValueError(f"Platform {platform_id} not found")

        # Decrypt credentials
        password = None
        private_key = None
        if platform.auth_method.value == "password" and platform.encrypted_password:
            password = crypto.decrypt_string(platform.encrypted_password)
        elif platform.auth_method.value == "private_key":
            # Get private key from SSHKey reference
            if platform.ssh_key_id:
                ssh_key = db.query(SSHKey).filter(SSHKey.id == platform.ssh_key_id).first()
                if ssh_key and ssh_key.encrypted_private_key:
                    private_key = crypto.decrypt_string(ssh_key.encrypted_private_key)
            elif platform.encrypted_private_key:
                # Legacy: use encrypted_private_key directly
                private_key = crypto.decrypt_string(platform.encrypted_private_key)

        # Connect via SSH
        ssh = SSHHelper(
            host=platform.host,
            port=platform.port,
            username=platform.username,
            password=password,
            private_key=private_key,
            known_host_fingerprint=platform.known_host_fingerprint,
        )

        success, error_msg = ssh.connect()
        if not success:
            raise Exception(f"SSH connection failed: {error_msg}")

        publish_task_message(task_id, "progress", "Connected. Running command...")

        # Execute command
        exit_code, stdout, stderr = ssh.execute_command(command, timeout)

        # Stream output
        if stdout:
            for line in stdout.split("\n"):
                if line:
                    publish_task_message(task_id, "stdout", line)

        if stderr:
            for line in stderr.split("\n"):
                if line:
                    publish_task_message(task_id, "stderr", line)

        ssh.close()

        # Save output (upload to S3 if large)
        result_location = None
        if len(stdout) + len(stderr) > 10000:  # If output > 10KB, upload to S3
            s3_key = f"tasks/{task_run_id}/output_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
            combined_output = f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}\n\n=== EXIT CODE ===\n{exit_code}"
            upload_to_s3(s3_key, combined_output)
            result_location = s3_key

        # Update task status
        task_run.status = TaskStatusEnum.SUCCESS if exit_code == 0 else TaskStatusEnum.FAILED
        task_run.finished_at = datetime.utcnow()
        task_run.stdout = stdout[:5000] if len(stdout) <= 5000 else stdout[:5000] + "... (truncated)"
        task_run.stderr = stderr[:5000] if len(stderr) <= 5000 else stderr[:5000] + "... (truncated)"
        task_run.result_location = result_location
        task_run.task_metadata = {"exit_code": exit_code}
        db.commit()

        status_msg = f"Command completed with exit code {exit_code}"
        publish_task_message(task_id, "done", status_msg)
        logger.info(f"Task {task_id} completed: {status_msg}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Task {task_id} failed: {error_msg}")

        # Update task status
        task_run = db.query(TaskRun).filter(TaskRun.id == task_run_id).first()
        if task_run:
            task_run.status = TaskStatusEnum.FAILED
            task_run.finished_at = datetime.utcnow()
            task_run.error_message = error_msg
            db.commit()

        publish_task_message(task_id, "error", f"Command execution failed: {error_msg}")
        raise
