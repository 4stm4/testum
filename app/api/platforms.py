"""Platforms API endpoints."""
import logging
import uuid
from typing import List

from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from app.audit import log_audit
from app.config import config
from app.crypto import crypto
from app.db import get_db
from app.models import (
    Platform,
    SSHKey,
    TaskRun,
    TaskStatusEnum,
    TaskTypeEnum,
    UserRole,
)
from app.pagination import get_pagination_params
from app.rbac import ALL_ROLES, get_request_user, require_roles
from app.schemas import (
    DeployKeysRequest,
    PlatformCreate,
    PlatformResponse,
    RunCommandRequest,
    TaskStatusResponse,
)
from app.tasks_new import deploy_keys_task, run_command_task

logger = logging.getLogger(__name__)

router = Router()


@require_roles(*ALL_ROLES)
async def list_platforms(request: Request):
    """List all platforms."""
    db: Session = next(get_db())
    try:
        try:
            limit, offset = get_pagination_params(request, default_limit=25)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        query = db.query(Platform)
        total = query.count()
        platforms: List[Platform] = (
            query.order_by(Platform.created_at.desc()).offset(offset).limit(limit).all()
        )
        result = []
        for platform in platforms:
            p_dict = PlatformResponse.model_validate(platform).model_dump(mode="json")
            p_dict["has_password"] = platform.encrypted_password is not None
            p_dict["has_private_key"] = (
                platform.ssh_key_id is not None or platform.encrypted_private_key is not None
            )
            p_dict["system_info"] = platform.system_info
            result.append(p_dict)

        response = JSONResponse(result)
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Limit"] = str(limit)
        response.headers["X-Offset"] = str(offset)
        return response
    finally:
        db.close()


@require_roles(UserRole.ADMIN, UserRole.OPERATOR)
async def create_platform(request: Request):
    """Create new platform."""
    db: Session = next(get_db())
    try:
        data = await request.json()
        logger.info(f"Received platform data: {data}")
        platform_data = PlatformCreate(**data)
        logger.info(f"Parsed platform_data.auth_method: {platform_data.auth_method}")

        # Validate auth method and credentials
        if platform_data.auth_method == "password" and not platform_data.password:
            return JSONResponse({"error": "Password required for password auth"}, status_code=400)
        if platform_data.auth_method == "private_key" and not platform_data.ssh_key_id:
            return JSONResponse({"error": "SSH Key required for private_key auth"}, status_code=400)

        system_info = None
        user = get_request_user(request)

        if config.APP_ENV != "testing":
            from app.ssh_helper import SSHHelper

            ssh = SSHHelper(
                host=platform_data.host,
                port=platform_data.port,
                username=platform_data.username,
            )

            try:
                if platform_data.auth_method == "password":
                    ssh.connect_with_password(platform_data.password)
                else:
                    ssh_key = db.query(SSHKey).filter(SSHKey.id == platform_data.ssh_key_id).first()
                    if not ssh_key:
                        return JSONResponse({"error": "SSH Key not found"}, status_code=400)

                    if not ssh_key.encrypted_private_key:
                        return JSONResponse({"error": "SSH Key has no private key for authentication"}, status_code=400)

                    private_key_str = crypto.decrypt_string(ssh_key.encrypted_private_key)
                    ssh.connect_with_key(private_key_str)

                exit_code, stdout, stderr = ssh.execute_command("echo 'Connection test successful'")
                if exit_code != 0:
                    raise Exception(f"Test command failed with exit code {exit_code}: {stderr}")
                logger.info("Connection test successful: %s", stdout.strip())

                system_info = {}
                try:
                    _, os_release, _ = ssh.execute_command("cat /etc/os-release 2>/dev/null || echo 'N/A'")
                    system_info["os_release"] = os_release.strip()

                    _, kernel, _ = ssh.execute_command("uname -r")
                    system_info["kernel"] = kernel.strip()

                    _, cpu_model, _ = ssh.execute_command("lscpu | grep 'Model name' | cut -d':' -f2 | xargs")
                    _, cpu_cores, _ = ssh.execute_command("nproc")
                    system_info["cpu"] = f"{cpu_model.strip()} ({cpu_cores.strip()} cores)"

                    _, memory, _ = ssh.execute_command("free -h | grep Mem | awk '{print $2\" total, \"$3\" used\"}'")
                    system_info["memory"] = memory.strip()

                    _, uptime, _ = ssh.execute_command("uptime -p 2>/dev/null || uptime")
                    system_info["uptime"] = uptime.strip()

                    logger.info("System info gathered: %s", system_info)
                except Exception as info_err:
                    logger.warning("Failed to gather some system info: %s", info_err)

            except Exception as conn_err:
                logger.error("Connection test failed: %s", conn_err)
                return JSONResponse(
                    {"error": "Connection test failed", "details": str(conn_err)},
                    status_code=400,
                )
            finally:
                ssh.close()

        # Encrypt password if provided
        encrypted_password = None
        if platform_data.password:
            encrypted_password = crypto.encrypt_string(platform_data.password)

        # Create platform
        new_platform = Platform(
            id=uuid.uuid4(),
            name=platform_data.name,
            host=platform_data.host,
            port=platform_data.port,
            username=platform_data.username,
            auth_method=platform_data.auth_method.lower(),
            encrypted_password=encrypted_password,
            ssh_key_id=platform_data.ssh_key_id,
            system_info=system_info or None,
        )

        db.add(new_platform)
        db.commit()
        db.refresh(new_platform)

        # Audit log
        log_audit(
            db,
            user=user.username if user else "system",
            action="create",
            object_type="platform",
            object_id=str(new_platform.id),
            meta={"name": new_platform.name, "host": new_platform.host},
        )

        response_data = PlatformResponse.model_validate(new_platform).model_dump(mode="json")
        response_data["has_password"] = new_platform.encrypted_password is not None
        response_data["has_private_key"] = new_platform.ssh_key_id is not None
        response_data["system_info"] = system_info  # Add system info from connection test

        return JSONResponse(response_data, status_code=201)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        db.close()


@require_roles(*ALL_ROLES)
async def get_platform(request: Request):
    """Get platform details."""
    platform_id = request.path_params["platform_id"]
    db: Session = next(get_db())
    try:
        platform = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            return JSONResponse({"error": "Platform not found"}, status_code=404)

        response_data = PlatformResponse.model_validate(platform).model_dump(mode="json")
        response_data["has_password"] = platform.encrypted_password is not None
        response_data["has_private_key"] = (
            platform.ssh_key_id is not None or platform.encrypted_private_key is not None
        )
        response_data["system_info"] = platform.system_info

        return JSONResponse(response_data)
    finally:
        db.close()


@require_roles(UserRole.ADMIN)
async def delete_platform(request: Request):
    """Delete platform."""
    platform_id = request.path_params["platform_id"]
    db: Session = next(get_db())
    try:
        platform = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            return JSONResponse({"error": "Platform not found"}, status_code=404)

        # Audit log
        user = get_request_user(request)
        log_audit(
            db,
            user=user.username if user else "system",
            action="delete",
            object_type="platform",
            object_id=str(platform.id),
            meta={"name": platform.name},
        )

        db.delete(platform)
        db.commit()

        return JSONResponse({"message": f"Platform {platform.name} deleted successfully"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        db.close()


@require_roles(UserRole.ADMIN, UserRole.OPERATOR)
async def deploy_keys(request: Request):
    """Deploy SSH keys to platform."""
    platform_id = request.path_params["platform_id"]
    db: Session = next(get_db())
    try:
        # Validate platform exists
        platform = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            return JSONResponse({"error": "Platform not found"}, status_code=404)

        # Parse request
        data = await request.json() if request.headers.get("content-length") else {}
        deploy_request = DeployKeysRequest(**data)

        # Validate key IDs if provided
        key_ids_str = None
        if deploy_request.key_ids:
            keys = db.query(SSHKey).filter(SSHKey.id.in_(deploy_request.key_ids)).all()
            if len(keys) != len(deploy_request.key_ids):
                return JSONResponse({"error": "Some key IDs not found"}, status_code=400)
            key_ids_str = [str(k) for k in deploy_request.key_ids]

        # Create task run record
        task_run = TaskRun(
            id=uuid.uuid4(),
            celery_task_id=None,  # Will be updated after Celery task starts
            type=TaskTypeEnum.DEPLOY,
            platform_id=platform_id,
            status=TaskStatusEnum.PENDING,
            task_metadata={"key_ids": key_ids_str} if key_ids_str else {},
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        # Start Celery task
        celery_task = deploy_keys_task.delay(str(task_run.id), platform_id, key_ids_str)

        # Update task_run with celery task ID
        task_run.celery_task_id = celery_task.id
        db.commit()

        # Audit log
        user = get_request_user(request)
        log_audit(
            db,
            user=user.username if user else "system",
            action="deploy_keys",
            object_type="platform",
            object_id=str(platform.id),
            meta={"task_id": celery_task.id},
        )

        return JSONResponse({
            "task_id": celery_task.id,
            "status": "pending",
            "message": "Key deployment task started",
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        db.close()


@require_roles(UserRole.ADMIN, UserRole.OPERATOR)
async def run_command(request: Request):
    """Run command on platform."""
    platform_id = request.path_params["platform_id"]
    db: Session = next(get_db())
    try:
        # Validate platform exists
        platform = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            return JSONResponse({"error": "Platform not found"}, status_code=404)

        # Parse request
        data = await request.json()
        command_request = RunCommandRequest(**data)

        # Create task run record
        task_run = TaskRun(
            id=uuid.uuid4(),
            celery_task_id=None,  # Will be updated after Celery task starts
            type=TaskTypeEnum.RUN_COMMAND,
            platform_id=platform_id,
            status=TaskStatusEnum.PENDING,
            task_metadata={"command": command_request.command, "timeout": command_request.timeout},
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        # Start Celery task
        celery_task = run_command_task.delay(
            str(task_run.id),
            platform_id,
            command_request.command,
            command_request.timeout,
        )

        # Update task_run with celery task ID
        task_run.celery_task_id = celery_task.id
        db.commit()

        # Audit log
        user = get_request_user(request)
        log_audit(
            db,
            user=user.username if user else "system",
            action="run_command",
            object_type="platform",
            object_id=str(platform.id),
            meta={"task_id": celery_task.id, "command": command_request.command},
        )

        return JSONResponse({
            "task_id": celery_task.id,
            "status": "pending",
            "message": "Command execution task started",
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        db.close()


async def get_task_status(request: Request):
    """Get task status."""
    task_id = request.path_params["task_id"]
    db: Session = next(get_db())
    try:
        task_run = db.query(TaskRun).filter(TaskRun.celery_task_id == task_id).first()
        if not task_run:
            return JSONResponse({"error": "Task not found"}, status_code=404)

        payload = TaskStatusResponse.model_validate(task_run).model_dump(mode="json")
        # TODO: Implement Taskiq result backend status check
        payload["celery_state"] = task_run.status.value if task_run.status else "unknown"

        return JSONResponse(payload)
    finally:
        db.close()


@require_roles(*ALL_ROLES)
async def list_tasks(request: Request):
    """List recent tasks with optional pagination."""
    db: Session = next(get_db())
    try:
        try:
            limit, offset = get_pagination_params(request, default_limit=50, max_limit=200)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        # Optional filter by status/type
        status_filter = request.query_params.get("status")
        type_filter = request.query_params.get("type")

        query = db.query(TaskRun)
        if status_filter:
            try:
                # Accept lowercase status values
                status_enum = TaskStatusEnum(status_filter)
                query = query.filter(TaskRun.status == status_enum)
            except Exception:
                return JSONResponse({"error": "Invalid status value"}, status_code=400)

        if type_filter:
            try:
                type_enum = TaskTypeEnum(type_filter)
                query = query.filter(TaskRun.type == type_enum)
            except Exception:
                return JSONResponse({"error": "Invalid type value"}, status_code=400)
        total = query.count()
        task_runs = (
            query.order_by(TaskRun.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for t in task_runs:
            item = TaskStatusResponse.model_validate(t).model_dump(mode="json")
            item["platform_name"] = t.platform.name if t.platform else None
            result.append(item)

        response = JSONResponse(result)
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Limit"] = str(limit)
        response.headers["X-Offset"] = str(offset)
        return response
    finally:
        db.close()


@require_roles(*ALL_ROLES)
async def get_platform_info(request: Request):
    """Get system information from platform."""
    platform_id = request.path_params["platform_id"]
    db: Session = next(get_db())
    
    try:
        platform = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            return JSONResponse({"error": "Platform not found"}, status_code=404)
        
        # Decrypt credentials
        password = None
        private_key = None
        
        if platform.auth_method.value == "password" and platform.encrypted_password:
            password = crypto.decrypt_string(platform.encrypted_password)
        elif platform.auth_method.value == "private_key":
            if platform.ssh_key_id:
                ssh_key = db.query(SSHKey).filter(SSHKey.id == platform.ssh_key_id).first()
                if ssh_key and ssh_key.encrypted_private_key:
                    private_key = crypto.decrypt_string(ssh_key.encrypted_private_key)
            elif platform.encrypted_private_key:
                private_key = crypto.decrypt_string(platform.encrypted_private_key)
        
        from app.ssh_helper import AsyncSSHClient

        ssh_kwargs = {
            "host": platform.host,
            "port": platform.port,
            "username": platform.username,
            "password": password,
            "private_key": private_key,
            "known_host_fingerprint": platform.known_host_fingerprint,
        }

        info = {}

        try:
            async with AsyncSSHClient(**ssh_kwargs) as ssh:
                _, os_release, _ = await ssh.execute_command(
                    "cat /etc/os-release 2>/dev/null || cat /etc/redhat-release 2>/dev/null || echo 'Unknown'"
                )
                info["os_release"] = os_release.strip()

                _, hostname, _ = await ssh.execute_command("hostname")
                info["hostname"] = hostname.strip()

                _, uptime, _ = await ssh.execute_command("uptime -p 2>/dev/null || uptime")
                info["uptime"] = uptime.strip()

                _, kernel, _ = await ssh.execute_command("uname -r")
                info["kernel"] = kernel.strip()

                _, cpu_info, _ = await ssh.execute_command(
                    "lscpu | grep 'Model name' | cut -d':' -f2 | xargs"
                )
                _, cpu_cores, _ = await ssh.execute_command("nproc")
                info["cpu"] = f"{cpu_info.strip()} ({cpu_cores.strip()} cores)"

                _, mem_info, _ = await ssh.execute_command(
                    "free -h | grep Mem | awk '{print $2\" total, \"$3\" used, \"$4\" free\"}'"
                )
                info["memory"] = mem_info.strip()

                _, disk_info, _ = await ssh.execute_command(
                    "df -h / | tail -1 | awk '{print $2\" total, \"$3\" used, \"$4\" free, \"$5\" used%\"}'"
                )
                info["disk"] = disk_info.strip()

                _, load_avg, _ = await ssh.execute_command(
                    "cat /proc/loadavg | awk '{print $1\" \"$2\" \"$3}'"
                )
                info["load_average"] = load_avg.strip()

                fingerprint = ssh.get_host_fingerprint()
                if fingerprint:
                    info["host_fingerprint"] = fingerprint
                    if not platform.known_host_fingerprint:
                        platform.known_host_fingerprint = fingerprint
                        db.commit()

                authorized_content = await ssh.read_file(
                    f"/home/{platform.username}/.ssh/authorized_keys"
                )
                if authorized_content:
                    keys = [line.strip() for line in authorized_content.splitlines() if line.strip()]
                    info["authorized_keys"] = len(keys)
                else:
                    info["authorized_keys"] = 0

                _, services, _ = await ssh.execute_command(
                    "systemctl list-units --type=service --state=running | head -n 5"
                )
                info["services"] = services.strip()

        except Exception as exc:
            logger.error("Failed to gather info from %s: %s", platform.host, exc)
            return JSONResponse(
                {"error": "Unable to fetch platform info", "details": str(exc)},
                status_code=400,
            )

        return JSONResponse({"system_info": info})
        
    except Exception as e:
        logger.error(f"Error getting platform info: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


@require_roles(UserRole.ADMIN, UserRole.OPERATOR)
async def revoke_task(request: Request):
    """Revoke (stop) a running task."""
    task_id = request.path_params["task_id"]
    db: Session = next(get_db())
    
    try:
        # Check if task exists in database
        task = db.query(TaskRun).filter(TaskRun.celery_task_id == task_id).first()
        if not task:
            return JSONResponse({"error": "Task not found"}, status_code=404)
        
        # Check if task is still running
        if task.status not in [TaskStatusEnum.pending, TaskStatusEnum.running]:
            return JSONResponse(
                {"error": f"Cannot stop task with status: {task.status}"}, 
                status_code=400
            )
        
        # TODO: Implement Taskiq task cancellation via result backend
        # For now, just mark as failed in database
        
        # Update task status in database
        task.status = TaskStatusEnum.failed
        task.error_message = "Task stopped by user"
        db.commit()
        
        # Audit log
        user = get_request_user(request)
        log_audit(
            db,
            user=user.username if user else "system",
            action="revoke_task",
            object_type="task",
            object_id=str(task.id),
            meta={"celery_task_id": task_id},
        )
        
        return JSONResponse({
            "message": "Task revoked successfully",
            "task_id": task_id,
            "status": "revoked"
        })
        
    except Exception as e:
        logger.error(f"Error revoking task {task_id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


# Routes
routes = [
    Route("/", list_platforms, methods=["GET"]),
    Route("/", create_platform, methods=["POST"]),
    Route("/{platform_id:uuid}", get_platform, methods=["GET"]),
    Route("/{platform_id:uuid}", delete_platform, methods=["DELETE"]),
    Route("/{platform_id:uuid}/deploy_keys", deploy_keys, methods=["POST"]),
    Route("/{platform_id:uuid}/run_command", run_command, methods=["POST"]),
    Route("/{platform_id:uuid}/info", get_platform_info, methods=["GET"]),
]

platforms_router = Router(routes=routes)

# Task status route (separate)
task_routes = [
    Route("/", list_tasks, methods=["GET"]),
    Route("/{task_id}", get_task_status, methods=["GET"]),
    Route("/{task_id}/revoke", revoke_task, methods=["POST"]),
]

tasks_router = Router(routes=task_routes)
