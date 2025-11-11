"""Platforms API endpoints."""
import uuid
import logging
from typing import List, Optional
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Router, Route
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Platform, TaskRun, TaskTypeEnum, TaskStatusEnum, SSHKey
from app.schemas import (
    PlatformCreate,
    PlatformResponse,
    DeployKeysRequest,
    RunCommandRequest,
    TaskResponse,
    TaskStatusResponse,
)
from app.crypto import crypto
from app.audit import log_audit
from app.tasks import deploy_keys_task, run_command_task

logger = logging.getLogger(__name__)

router = Router()


async def list_platforms(request: Request):
    """List all platforms."""
    db: Session = next(get_db())
    try:
        platforms = db.query(Platform).all()
        result = []
        for platform in platforms:
            p_dict = PlatformResponse.model_validate(platform).model_dump(mode="json")
            p_dict["has_password"] = platform.encrypted_password is not None
            p_dict["has_private_key"] = platform.encrypted_private_key is not None
            result.append(p_dict)
        return JSONResponse(result)
    finally:
        db.close()


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
        )

        db.add(new_platform)
        db.commit()
        db.refresh(new_platform)

        # Audit log
        log_audit(
            db,
            user=request.state.user if hasattr(request.state, "user") else "admin",
            action="create",
            object_type="platform",
            object_id=str(new_platform.id),
            meta={"name": new_platform.name, "host": new_platform.host},
        )

        response_data = PlatformResponse.model_validate(new_platform).model_dump(mode="json")
        response_data["has_password"] = new_platform.encrypted_password is not None
        response_data["has_private_key"] = new_platform.ssh_key_id is not None

        return JSONResponse(response_data, status_code=201)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        db.close()


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
        response_data["has_private_key"] = platform.encrypted_private_key is not None

        return JSONResponse(response_data)
    finally:
        db.close()


async def delete_platform(request: Request):
    """Delete platform."""
    platform_id = request.path_params["platform_id"]
    db: Session = next(get_db())
    try:
        platform = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            return JSONResponse({"error": "Platform not found"}, status_code=404)

        # Audit log
        log_audit(
            db,
            user=request.state.user if hasattr(request.state, "user") else "admin",
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
            celery_task_id="pending",  # Will be updated
            type=TaskTypeEnum.DEPLOY,
            platform_id=platform_id,
            status=TaskStatusEnum.PENDING,
            metadata={"key_ids": key_ids_str} if key_ids_str else {},
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
        log_audit(
            db,
            user=request.state.user if hasattr(request.state, "user") else "admin",
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
            celery_task_id="pending",
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
        log_audit(
            db,
            user=request.state.user if hasattr(request.state, "user") else "admin",
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

        return JSONResponse(TaskStatusResponse.model_validate(task_run).model_dump(mode="json"))
    finally:
        db.close()


async def get_platform_info(request: Request):
    """Get system information from platform."""
    platform_id = request.path_params["platform_id"]
    db: Session = next(get_db())
    
    try:
        platform = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            return JSONResponse({"error": "Platform not found"}, status_code=404)
        
        # Decrypt credentials
        from app import crypto
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
        
        # Connect and gather info
        from app.ssh_helper import SSHHelper
        ssh = SSHHelper(
            host=platform.host,
            port=platform.port,
            username=platform.username,
            password=password,
            private_key=private_key,
        )
        
        info = {}
        
        try:
            ssh.connect()
            
            # Get OS info
            os_release = ssh.execute_command("cat /etc/os-release 2>/dev/null || cat /etc/redhat-release 2>/dev/null || echo 'Unknown'")
            info["os_release"] = os_release.strip()
            
            # Get hostname
            hostname = ssh.execute_command("hostname")
            info["hostname"] = hostname.strip()
            
            # Get uptime
            uptime = ssh.execute_command("uptime -p 2>/dev/null || uptime")
            info["uptime"] = uptime.strip()
            
            # Get kernel
            kernel = ssh.execute_command("uname -r")
            info["kernel"] = kernel.strip()
            
            # Get CPU info
            cpu_info = ssh.execute_command("lscpu | grep 'Model name' | cut -d':' -f2 | xargs")
            cpu_cores = ssh.execute_command("nproc")
            info["cpu"] = f"{cpu_info.strip()} ({cpu_cores.strip()} cores)"
            
            # Get memory
            mem_info = ssh.execute_command("free -h | grep Mem | awk '{print $2\" total, \"$3\" used, \"$4\" free\"}'")
            info["memory"] = mem_info.strip()
            
            # Get disk
            disk_info = ssh.execute_command("df -h / | tail -1 | awk '{print $2\" total, \"$3\" used, \"$4\" free, \"$5\" used%\"}'")
            info["disk"] = disk_info.strip()
            
            # Get load average
            load_avg = ssh.execute_command("cat /proc/loadavg | awk '{print $1\" \"$2\" \"$3}'")
            info["load_average"] = load_avg.strip()
            
            info["status"] = "online"
            
        except Exception as e:
            logger.error(f"Failed to gather info from {platform.host}: {e}")
            info["status"] = "offline"
            info["error"] = str(e)
        finally:
            ssh.disconnect()
        
        return JSONResponse(info)
        
    except Exception as e:
        logger.error(f"Error getting platform info: {e}")
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
    Route("/{task_id}", get_task_status, methods=["GET"]),
]

tasks_router = Router(routes=task_routes)
