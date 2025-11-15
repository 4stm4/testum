# SPDX-License-Identifier: MIT
"""GitOps Import API - import platforms and SSH keys from Git repository."""
import json
import shutil
import tempfile
import yaml
from pathlib import Path
from typing import Dict, Any

from sqlalchemy.orm import Session
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.db import get_db
from app.models import Platform, SSHKey, UserRole
from app.rbac import require_roles


def clone_git_repo(git_url: str, branch: str = "main", username: str = None, token: str = None) -> Path:
    """
    Clone a Git repository to a temporary directory.
    
    Args:
        git_url: Git repository URL (https or git protocol)
        branch: Branch to clone (default: main)
        username: Optional username for authentication
        token: Optional token/password for authentication
    
    Returns:
        Path to the cloned repository
    """
    import subprocess
    
    temp_dir = Path(tempfile.mkdtemp(prefix="testum_gitops_"))
    
    # Build git clone command
    cmd = ["git", "clone", "--depth", "1", "--branch", branch]
    
    # Add authentication if provided
    if username and token:
        # Insert credentials into URL
        if git_url.startswith("https://"):
            auth_url = git_url.replace("https://", f"https://{username}:{token}@")
            cmd.extend([auth_url, str(temp_dir)])
        else:
            cmd.extend([git_url, str(temp_dir)])
    else:
        cmd.extend([git_url, str(temp_dir)])
    
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=True
        )
        return temp_dir
    except subprocess.CalledProcessError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError(f"Git clone failed: {exc.stderr}")
    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError("Git clone timed out (60s)")


def parse_config_file(file_path: Path) -> Dict[str, Any]:
    """
    Parse configuration file (YAML or JSON).
    
    Args:
        file_path: Path to configuration file
    
    Returns:
        Parsed configuration dictionary
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Try YAML first, then JSON
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            raise ValueError(f"Failed to parse {file_path.name} as YAML or JSON")


def import_platforms_from_config(db: Session, config: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """
    Import platforms from configuration dictionary.
    
    Args:
        db: Database session
        config: Configuration dictionary with 'platforms' key
        dry_run: If True, only validate without importing
    
    Returns:
        Import statistics
    """
    stats = {
        "platforms_imported": 0,
        "platforms_skipped": 0,
        "ssh_keys_imported": 0,
        "ssh_keys_skipped": 0,
        "errors": [],
    }
    
    # Import SSH keys first (if present)
    if "ssh_keys" in config:
        for key_data in config["ssh_keys"]:
            try:
                # Check if key already exists
                existing_key = db.query(SSHKey).filter(SSHKey.name == key_data["name"]).first()
                if existing_key:
                    stats["ssh_keys_skipped"] += 1
                    continue
                
                if not dry_run:
                    ssh_key = SSHKey(
                        name=key_data["name"],
                        public_key=key_data.get("public_key", ""),
                        description=key_data.get("description"),
                    )
                    db.add(ssh_key)
                    db.flush()  # Get ID for platforms
                
                stats["ssh_keys_imported"] += 1
            except Exception as exc:
                stats["errors"].append(f"SSH key '{key_data.get('name', 'unknown')}': {str(exc)}")
    
    # Import platforms
    if "platforms" in config:
        for platform_data in config["platforms"]:
            try:
                # Check if platform already exists
                existing_platform = db.query(Platform).filter(
                    Platform.name == platform_data["name"]
                ).first()
                
                if existing_platform:
                    stats["platforms_skipped"] += 1
                    continue
                
                # Resolve SSH key reference
                ssh_key_id = None
                if platform_data.get("ssh_key_name"):
                    ssh_key = db.query(SSHKey).filter(
                        SSHKey.name == platform_data["ssh_key_name"]
                    ).first()
                    if ssh_key:
                        ssh_key_id = ssh_key.id
                elif platform_data.get("ssh_key_id"):
                    ssh_key_id = platform_data["ssh_key_id"]
                
                if not dry_run:
                    platform = Platform(
                        name=platform_data["name"],
                        host=platform_data["host"],
                        port=platform_data.get("port", 22),
                        username=platform_data["username"],
                        auth_method=platform_data.get("auth_method", "password"),
                        ssh_key_id=ssh_key_id,
                        description=platform_data.get("description"),
                        known_host_fingerprint=platform_data.get("known_host_fingerprint"),
                    )
                    db.add(platform)
                
                stats["platforms_imported"] += 1
            except Exception as exc:
                stats["errors"].append(f"Platform '{platform_data.get('name', 'unknown')}': {str(exc)}")
    
    if not dry_run:
        db.commit()
    
    return stats


@require_roles(UserRole.ADMIN)
async def gitops_import(request: Request):
    """
    Import configuration from Git repository.
    
    Expected JSON body:
    {
        "git_url": "https://github.com/user/repo.git",
        "branch": "main",
        "config_path": "testum-config.yaml",  // Optional, default: testum-config.yaml
        "username": "git_username",  // Optional
        "token": "git_token",  // Optional
        "dry_run": false  // Optional, default: false
    }
    """
    db: Session = next(get_db())
    try:
        body = await request.json()
        
        git_url = body.get("git_url")
        if not git_url:
            return JSONResponse({"error": "git_url is required"}, status_code=400)
        
        branch = body.get("branch", "main")
        config_path = body.get("config_path", "testum-config.yaml")
        username = body.get("username")
        token = body.get("token")
        dry_run = body.get("dry_run", False)
        
        # Clone repository
        try:
            repo_dir = clone_git_repo(git_url, branch, username, token)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        
        try:
            # Find and parse config file
            config_file = repo_dir / config_path
            if not config_file.exists():
                # Try alternative locations
                alternatives = [
                    repo_dir / "testum.yaml",
                    repo_dir / "testum-config.yml",
                    repo_dir / "config" / "testum.yaml",
                    repo_dir / ".testum" / "config.yaml",
                ]
                for alt in alternatives:
                    if alt.exists():
                        config_file = alt
                        break
                else:
                    return JSONResponse(
                        {"error": f"Configuration file not found: {config_path}"},
                        status_code=404
                    )
            
            # Parse configuration
            try:
                config = parse_config_file(config_file)
            except ValueError as exc:
                return JSONResponse({"error": str(exc)}, status_code=400)
            
            # Import configuration
            stats = import_platforms_from_config(db, config, dry_run=dry_run)
            
            return JSONResponse({
                "success": True,
                "dry_run": dry_run,
                "git_url": git_url,
                "branch": branch,
                "config_file": config_file.name,
                **stats
            })
        
        finally:
            # Cleanup temporary directory
            shutil.rmtree(repo_dir, ignore_errors=True)
    
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    
    finally:
        db.close()


# Router
gitops_router = Starlette(
    routes=[
        Route("/import", gitops_import, methods=["POST"]),
    ]
)
