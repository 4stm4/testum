# SPDX-License-Identifier: MIT
"""Backup and restore configuration API."""
import io
import yaml
from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy.orm import Session
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from app.db import get_db
from app.models import AutomationJob, AutomationJobPlatform, Platform, Script, SSHKey, User, UserRole
from app.rbac import require_roles


@require_roles(UserRole.ADMIN)
async def export_backup(request: Request):
    """Export full configuration to YAML."""
    db: Session = next(get_db())
    try:
        backup_data: Dict[str, Any] = {
            "metadata": {
                "version": "0.1.0",
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "exported_by": request.state.user.username if hasattr(request.state, 'user') else "unknown",
            },
            "ssh_keys": [],
            "platforms": [],
            "scripts": [],
            "automations": [],
            "users": [],
        }

        # Build SSH key id→name map for resolving platform references
        keys = db.query(SSHKey).all()
        key_id_to_name: Dict[str, str] = {}
        for key in keys:
            backup_data["ssh_keys"].append({
                "name": key.name,
                "public_key": key.public_key,
            })
            key_id_to_name[str(key.id)] = key.name

        # Export platforms — store ssh_key_name instead of UUID so import can resolve it
        platforms = db.query(Platform).all()
        platform_id_to_name: Dict[str, str] = {}
        for platform in platforms:
            platform_id_to_name[str(platform.id)] = platform.name
            backup_data["platforms"].append({
                "name": platform.name,
                "host": platform.host,
                "port": platform.port,
                "username": platform.username,
                "auth_method": platform.auth_method.value if hasattr(platform.auth_method, "value") else str(platform.auth_method),
                "ssh_key_name": key_id_to_name.get(str(platform.ssh_key_id)) if platform.ssh_key_id else None,
                "known_host_fingerprint": platform.known_host_fingerprint,
                # Note: encrypted_password is NOT exported for security
            })

        # Export scripts
        scripts = db.query(Script).all()
        script_id_to_name: Dict[str, str] = {}
        for script in scripts:
            script_id_to_name[str(script.id)] = script.name
            backup_data["scripts"].append({
                "name": script.name,
                "language": script.language,
                "content": script.content,
            })

        # Export automations (without platform UUIDs — use names)
        jobs = db.query(AutomationJob).all()
        for job in jobs:
            target_platform_names = [
                platform_id_to_name.get(str(link.platform_id), str(link.platform_id))
                for link in job.platform_links
            ]
            backup_data["automations"].append({
                "name": job.name,
                "description": job.description,
                "execution_type": job.execution_type.value if hasattr(job.execution_type, "value") else str(job.execution_type),
                "command": job.command,
                "script_name": script_id_to_name.get(str(job.script_id)) if job.script_id else None,
                "trigger_type": job.trigger_type.value if hasattr(job.trigger_type, "value") else str(job.trigger_type),
                "cron_expression": job.cron_expression,
                "repository_url": job.repository_url,
                "repository_branch": job.repository_branch,
                "run_on_all_platforms": job.run_on_all_platforms,
                "target_platform_names": target_platform_names,
                "environment": job.environment,
                "tags": job.tags,
                "notification_settings": job.notification_settings,
                "timeout_seconds": job.timeout_seconds,
                "max_retries": job.max_retries,
                "retry_delay_seconds": job.retry_delay_seconds,
                "require_approval": job.require_approval,
                "is_enabled": job.is_enabled,
                "notes": job.notes,
                # webhook_secret NOT exported for security
            })

        # Export users (without passwords)
        users = db.query(User).all()
        for user in users:
            backup_data["users"].append({
                "username": user.username,
                "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
                "is_active": user.is_active,
                # Note: hashed_password is NOT exported
            })

        yaml_content = yaml.dump(backup_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        filename = f"testum_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.yaml"

        return StreamingResponse(
            io.BytesIO(yaml_content.encode('utf-8')),
            media_type="application/x-yaml",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    finally:
        db.close()


@require_roles(UserRole.ADMIN)
async def import_backup(request: Request):
    """Import configuration from YAML."""
    db: Session = next(get_db())
    try:
        body = await request.body()
        backup_data = yaml.safe_load(body.decode('utf-8'))

        if not isinstance(backup_data, dict):
            return JSONResponse({"error": "Invalid YAML format"}, status_code=400)

        stats = {
            "platforms_imported": 0,
            "ssh_keys_imported": 0,
            "scripts_imported": 0,
            "automations_imported": 0,
            "users_imported": 0,
            "errors": [],
        }

        # --- SSH keys ---
        if "ssh_keys" in backup_data:
            for key_data in backup_data["ssh_keys"]:
                try:
                    existing = db.query(SSHKey).filter(SSHKey.name == key_data["name"]).first()
                    if existing:
                        stats["errors"].append(f"SSH key '{key_data['name']}' already exists, skipping")
                        continue
                    db.add(SSHKey(name=key_data["name"], public_key=key_data["public_key"]))
                    stats["ssh_keys_imported"] += 1
                except Exception as e:
                    stats["errors"].append(f"Failed to import SSH key '{key_data.get('name')}': {str(e)}")

        db.flush()

        # --- Platforms ---
        if "platforms" in backup_data:
            for platform_data in backup_data["platforms"]:
                try:
                    existing = db.query(Platform).filter(Platform.name == platform_data["name"]).first()
                    if existing:
                        stats["errors"].append(f"Platform '{platform_data['name']}' already exists, skipping")
                        continue

                    # Resolve SSH key by name
                    ssh_key_id = None
                    ssh_key_name = platform_data.get("ssh_key_name")
                    if ssh_key_name:
                        key = db.query(SSHKey).filter(SSHKey.name == ssh_key_name).first()
                        if key:
                            ssh_key_id = key.id
                        else:
                            stats["errors"].append(f"SSH key '{ssh_key_name}' not found for platform '{platform_data['name']}' — link skipped")

                    db.add(Platform(
                        name=platform_data["name"],
                        host=platform_data["host"],
                        port=platform_data.get("port", 22),
                        username=platform_data["username"],
                        auth_method=platform_data.get("auth_method", "password"),
                        ssh_key_id=ssh_key_id,
                        known_host_fingerprint=platform_data.get("known_host_fingerprint"),
                    ))
                    stats["platforms_imported"] += 1
                except Exception as e:
                    stats["errors"].append(f"Failed to import platform '{platform_data.get('name')}': {str(e)}")

        db.flush()

        # --- Scripts ---
        if "scripts" in backup_data:
            for script_data in backup_data["scripts"]:
                try:
                    existing = db.query(Script).filter(Script.name == script_data["name"]).first()
                    if existing:
                        stats["errors"].append(f"Script '{script_data['name']}' already exists, skipping")
                        continue
                    db.add(Script(
                        name=script_data["name"],
                        language=script_data.get("language", "bash"),
                        content=script_data.get("content", ""),
                    ))
                    stats["scripts_imported"] += 1
                except Exception as e:
                    stats["errors"].append(f"Failed to import script '{script_data.get('name')}': {str(e)}")

        db.flush()

        # --- Automations ---
        if "automations" in backup_data:
            for job_data in backup_data["automations"]:
                try:
                    existing = db.query(AutomationJob).filter(AutomationJob.name == job_data["name"]).first()
                    if existing:
                        stats["errors"].append(f"Automation '{job_data['name']}' already exists, skipping")
                        continue

                    script_id = None
                    if job_data.get("script_name"):
                        script = db.query(Script).filter(Script.name == job_data["script_name"]).first()
                        if script:
                            script_id = script.id
                        else:
                            stats["errors"].append(f"Script '{job_data['script_name']}' not found for automation '{job_data['name']}' — link skipped")

                    job = AutomationJob(
                        name=job_data["name"],
                        description=job_data.get("description"),
                        execution_type=job_data.get("execution_type", "command"),
                        command=job_data.get("command"),
                        script_id=script_id,
                        trigger_type=job_data.get("trigger_type", "manual"),
                        cron_expression=job_data.get("cron_expression"),
                        repository_url=job_data.get("repository_url"),
                        repository_branch=job_data.get("repository_branch"),
                        run_on_all_platforms=job_data.get("run_on_all_platforms", False),
                        environment=job_data.get("environment"),
                        tags=job_data.get("tags"),
                        notification_settings=job_data.get("notification_settings"),
                        timeout_seconds=job_data.get("timeout_seconds", 600),
                        max_retries=job_data.get("max_retries", 0),
                        retry_delay_seconds=job_data.get("retry_delay_seconds", 60),
                        require_approval=job_data.get("require_approval", False),
                        is_enabled=job_data.get("is_enabled", True),
                        notes=job_data.get("notes"),
                    )
                    db.add(job)
                    db.flush()

                    # Restore platform links by name
                    for platform_name in (job_data.get("target_platform_names") or []):
                        platform = db.query(Platform).filter(Platform.name == platform_name).first()
                        if platform:
                            db.add(AutomationJobPlatform(job_id=job.id, platform_id=platform.id))
                        else:
                            stats["errors"].append(f"Platform '{platform_name}' not found for automation '{job_data['name']}' — link skipped")

                    stats["automations_imported"] += 1
                except Exception as e:
                    stats["errors"].append(f"Failed to import automation '{job_data.get('name')}': {str(e)}")

        # Users import not supported for security
        if "users" in backup_data:
            stats["errors"].append("User import is not supported for security reasons. Create users manually.")

        db.commit()

        return JSONResponse({
            "message": "Backup imported successfully",
            "stats": stats,
        })

    except yaml.YAMLError as e:
        return JSONResponse({"error": f"Invalid YAML: {str(e)}"}, status_code=400)
    except Exception as e:
        db.rollback()
        return JSONResponse({"error": f"Import failed: {str(e)}"}, status_code=500)
    finally:
        db.close()


# Router
backup_router = Starlette(
    routes=[
        Route("/export", export_backup, methods=["GET"]),
        Route("/import", import_backup, methods=["POST"]),
    ]
)
