import logging
logger = logging.getLogger(__name__)
from datetime import datetime
import boto3
from botocore.client import Config
from app.config import config
from app.db import SessionLocal
from app.models import Platform, SSHKey, TaskRun, TaskStatusEnum
from app.crypto import crypto
from app.ssh_helper import AsyncSSHClient
from pyjobkit.contracts import Executor, ExecContext

# Executor для деплоя ключей
class DeployKeysExecutor(Executor):
    kind = "deploy_keys"

    async def run(self, *, job_id, payload, ctx: ExecContext):
        task_run_id = payload["task_run_id"]
        platform_id = payload["platform_id"]
        key_ids = payload.get("key_ids")
        db = SessionLocal()
        try:
            task_run = db.query(TaskRun).filter(TaskRun.id == task_run_id).first()
            if not task_run:
                raise ValueError(f"TaskRun {task_run_id} not found")
            task_run.status = TaskStatusEnum.RUNNING
            task_run.started_at = datetime.utcnow()
            db.commit()
            await ctx.log("Starting key deployment...")
            platform = db.query(Platform).filter(Platform.id == platform_id).first()
            if not platform:
                raise ValueError(f"Platform {platform_id} not found")
            await ctx.log(f"Connecting to {platform.name}...")
            if key_ids:
                keys = db.query(SSHKey).filter(SSHKey.id.in_(key_ids)).all()
            else:
                keys = db.query(SSHKey).all()
            if not keys:
                raise ValueError("No SSH keys found to deploy")
            await ctx.log(f"Found {len(keys)} keys to deploy")
            ssh_client = AsyncSSHClient()
            if platform.auth_method == "password":
                password = crypto.decrypt(platform.password)
                await ssh_client.connect_with_password(
                    host=platform.host,
                    port=platform.port,
                    username=platform.username,
                    password=password
                )
            else:
                key = db.query(SSHKey).filter(SSHKey.id == platform.ssh_key_id).first()
                if not key or not key.private_key:
                    raise ValueError("SSH key not found or has no private key")
                private_key_data = crypto.decrypt(key.private_key)
                await ssh_client.connect_with_key(
                    host=platform.host,
                    port=platform.port,
                    username=platform.username,
                    private_key_data=private_key_data
                )
            await ctx.log("Connected to platform")
            deployed_count = 0
            output_lines = []
            for key in keys:
                await ctx.log(f"Deploying key: {key.name}")
                cmd = f'mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo "{key.public_key}" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
                stdout, stderr = await ssh_client.execute_command(cmd)
                if stderr:
                    output_lines.append(f"[{key.name}] stderr: {stderr}")
                    await ctx.log(f"[{key.name}] {stderr}")
                output_lines.append(f"[{key.name}] Deployed successfully")
                await ctx.log(f"[{key.name}] Deployed successfully")
                deployed_count += 1
            await ssh_client.close()
            output_content = "\n".join(output_lines)
            s3_key = f"tasks/{task_run_id}/output.txt"
            upload_to_s3(s3_key, output_content)
            task_run.status = TaskStatusEnum.SUCCESS
            task_run.completed_at = datetime.utcnow()
            task_run.output_s3_key = s3_key
            db.commit()
            await ctx.log(f"Deployed {deployed_count} keys successfully")
            return {"task_id": job_id, "status": "success"}
        except Exception as e:
            logger.exception(f"Task {task_run_id} failed")
            task_run = db.query(TaskRun).filter(TaskRun.id == task_run_id).first()
            if task_run:
                task_run.status = TaskStatusEnum.FAILED
                task_run.completed_at = datetime.utcnow()
                task_run.error = str(e)
                db.commit()
            await ctx.log(f"error: {str(e)}")
            raise
        finally:
            db.close()

# Executor для запуска команды
class RunCommandExecutor(Executor):
    kind = "run_command"

    async def run(self, *, job_id, payload, ctx: ExecContext):
        task_run_id = payload["task_run_id"]
        platform_id = payload["platform_id"]
        command = payload["command"]
        db = SessionLocal()
        try:
            task_run = db.query(TaskRun).filter(TaskRun.id == task_run_id).first()
            if not task_run:
                raise ValueError(f"TaskRun {task_run_id} not found")
            task_run.status = TaskStatusEnum.RUNNING
            task_run.started_at = datetime.utcnow()
            db.commit()
            await ctx.log("Starting command execution...")
            platform = db.query(Platform).filter(Platform.id == platform_id).first()
            if not platform:
                raise ValueError(f"Platform {platform_id} not found")
            await ctx.log(f"Connecting to {platform.name}...")
            ssh_client = AsyncSSHClient()
            if platform.auth_method == "password":
                password = crypto.decrypt(platform.password)
                await ssh_client.connect_with_password(
                    host=platform.host,
                    port=platform.port,
                    username=platform.username,
                    password=password
                )
            else:
                key = db.query(SSHKey).filter(SSHKey.id == platform.ssh_key_id).first()
                if not key or not key.private_key:
                    raise ValueError("SSH key not found or has no private key")
                private_key_data = crypto.decrypt(key.private_key)
                await ssh_client.connect_with_key(
                    host=platform.host,
                    port=platform.port,
                    username=platform.username,
                    private_key_data=private_key_data
                )
            await ctx.log("Connected, executing command...")
            await ctx.log(f"$ {command}\n")
            stdout, stderr = await ssh_client.execute_command(command)
            if stdout:
                await ctx.log(stdout)
            if stderr:
                await ctx.log(stderr)
            await ssh_client.close()
            output_content = f"Command: {command}\n\n=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}"
            s3_key = f"tasks/{task_run_id}/output.txt"
            upload_to_s3(s3_key, output_content)
            task_run.status = TaskStatusEnum.SUCCESS
            task_run.completed_at = datetime.utcnow()
            task_run.output_s3_key = s3_key
            db.commit()
            await ctx.log("Command executed successfully")
            return {"task_id": job_id, "status": "success"}
        except Exception as e:
            logger.exception(f"Task {task_run_id} failed")
            task_run = db.query(TaskRun).filter(TaskRun.id == task_run_id).first()
            if task_run:
                task_run.status = TaskStatusEnum.FAILED
                task_run.completed_at = datetime.utcnow()
## executor будет реализован ниже
                task_run.error = str(e)
                db.commit()
            await ctx.log(f"error: {str(e)}")
            raise
        finally:
            db.close()



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


