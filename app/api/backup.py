# SPDX-License-Identifier: MIT
"""Backup and restore configuration API."""
import io
import yaml
from datetime import datetime
from typing import Dict, Any

from sqlalchemy.orm import Session
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from app.db import get_db
from app.models import Platform, SSHKey, User, UserRole
from app.rbac import require_roles


@require_roles(UserRole.ADMIN)
async def export_backup(request: Request):
    """Export full configuration to YAML."""
    db: Session = next(get_db())
    try:
        backup_data: Dict[str, Any] = {
            "metadata": {
                "version": "0.1.0",
                "exported_at": datetime.utcnow().isoformat(),
                "exported_by": request.state.user.username if hasattr(request.state, 'user') else "unknown",
            },
            "platforms": [],
            "ssh_keys": [],
            "users": [],
        }

        # Export platforms (without decrypted passwords)
        platforms = db.query(Platform).all()
        for platform in platforms:
            backup_data["platforms"].append({
                "name": platform.name,
                "host": platform.host,
                "port": platform.port,
                "username": platform.username,
                "auth_method": platform.auth_method,
                "ssh_key_id": str(platform.ssh_key_id) if platform.ssh_key_id else None,
                "known_host_fingerprint": platform.known_host_fingerprint,
                "description": platform.description,
                # Note: encrypted_password is NOT exported for security
            })

        # Export SSH keys (public keys only)
        keys = db.query(SSHKey).all()
        for key in keys:
            backup_data["ssh_keys"].append({
                "name": key.name,
                "public_key": key.public_key,
                "description": key.description,
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

        # Convert to YAML
        yaml_content = yaml.dump(backup_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        filename = f"testum_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.yaml"

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
        # Parse YAML from request body
        body = await request.body()
        backup_data = yaml.safe_load(body.decode('utf-8'))

        if not isinstance(backup_data, dict):
            return JSONResponse({"error": "Invalid YAML format"}, status_code=400)

        stats = {
            "platforms_imported": 0,
            "ssh_keys_imported": 0,
            "users_imported": 0,
            "errors": [],
        }

        # Import SSH keys first (platforms may reference them)
        if "ssh_keys" in backup_data:
            for key_data in backup_data["ssh_keys"]:
                try:
                    # Check if key already exists
                    existing = db.query(SSHKey).filter(SSHKey.name == key_data["name"]).first()
                    if existing:
                        stats["errors"].append(f"SSH key '{key_data['name']}' already exists, skipping")
                        continue

                    new_key = SSHKey(
                        name=key_data["name"],
                        public_key=key_data["public_key"],
                        description=key_data.get("description"),
                    )
                    db.add(new_key)
                    stats["ssh_keys_imported"] += 1
                except Exception as e:
                    stats["errors"].append(f"Failed to import SSH key '{key_data.get('name')}': {str(e)}")

        db.flush()  # Commit keys before platforms

        # Import platforms
        if "platforms" in backup_data:
            for platform_data in backup_data["platforms"]:
                try:
                    # Check if platform already exists
                    existing = db.query(Platform).filter(Platform.name == platform_data["name"]).first()
                    if existing:
                        stats["errors"].append(f"Platform '{platform_data['name']}' already exists, skipping")
                        continue

                    # Resolve SSH key if referenced
                    ssh_key_id = None
                    if platform_data.get("ssh_key_id"):
                        # Try to find key by name (since IDs may differ)
                        # This is a limitation - we can't reliably restore key references
                        pass

                    new_platform = Platform(
                        name=platform_data["name"],
                        host=platform_data["host"],
                        port=platform_data.get("port", 22),
                        username=platform_data["username"],
                        auth_method=platform_data.get("auth_method", "password"),
                        ssh_key_id=ssh_key_id,
                        known_host_fingerprint=platform_data.get("known_host_fingerprint"),
                        description=platform_data.get("description"),
                        # Note: passwords must be set manually after import
                    )
                    db.add(new_platform)
                    stats["platforms_imported"] += 1
                except Exception as e:
                    stats["errors"].append(f"Failed to import platform '{platform_data.get('name')}': {str(e)}")

        # Import users (skipped - too sensitive, must be created manually)
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
