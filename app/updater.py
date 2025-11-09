"""GitHub updater module for checking and applying updates."""
import logging
import subprocess
import os
from typing import Optional, Dict, Any
import httpx
from packaging import version

logger = logging.getLogger(__name__)

# Current version
CURRENT_VERSION = "0.1.0"

# GitHub repository
GITHUB_OWNER = "4stm4"
GITHUB_REPO = "testum"


class UpdateError(Exception):
    """Custom exception for update errors."""
    pass


async def check_for_updates() -> Dict[str, Any]:
    """
    Check GitHub for newer versions.
    
    Returns:
        Dict with update information:
        {
            "update_available": bool,
            "current_version": str,
            "latest_version": str,
            "release_url": str,
            "release_notes": str,
            "published_at": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            
            if response.status_code == 404:
                # No releases yet
                return {
                    "update_available": False,
                    "current_version": CURRENT_VERSION,
                    "latest_version": None,
                    "message": "No releases found on GitHub",
                }
            
            response.raise_for_status()
            release_data = response.json()
            
            latest_version = release_data.get("tag_name", "").lstrip("v")
            release_url = release_data.get("html_url", "")
            release_notes = release_data.get("body", "")
            published_at = release_data.get("published_at", "")
            
            # Compare versions
            current = version.parse(CURRENT_VERSION)
            latest = version.parse(latest_version) if latest_version else current
            
            update_available = latest > current
            
            return {
                "update_available": update_available,
                "current_version": CURRENT_VERSION,
                "latest_version": latest_version,
                "release_url": release_url,
                "release_notes": release_notes,
                "published_at": published_at,
            }
            
    except httpx.HTTPError as e:
        logger.error(f"HTTP error checking for updates: {e}")
        raise UpdateError(f"Failed to check for updates: {str(e)}")
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        raise UpdateError(f"Unexpected error: {str(e)}")


async def get_current_branch() -> str:
    """Get current git branch."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=os.getcwd()
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get current branch: {e}")
        return "main"


async def get_current_commit() -> str:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=os.getcwd()
        )
        return result.stdout.strip()[:7]
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get current commit: {e}")
        return "unknown"


async def check_git_status() -> Dict[str, Any]:
    """Check if working directory is clean."""
    try:
        # Check for uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=os.getcwd()
        )
        
        has_changes = bool(result.stdout.strip())
        
        return {
            "clean": not has_changes,
            "uncommitted_changes": result.stdout.strip().split("\n") if has_changes else []
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to check git status: {e}")
        raise UpdateError(f"Failed to check git status: {str(e)}")


async def perform_update(target_version: Optional[str] = None) -> Dict[str, Any]:
    """
    Perform git pull to update the application.
    
    Args:
        target_version: Specific version tag to checkout (e.g., "v0.2.0")
                       If None, pulls latest from current branch
    
    Returns:
        Dict with update results
    """
    try:
        # Check if working directory is clean
        status = await check_git_status()
        if not status["clean"]:
            raise UpdateError(
                "Working directory has uncommitted changes. "
                "Please commit or stash them first."
            )
        
        # Get current state
        current_branch = await get_current_branch()
        current_commit = await get_current_commit()
        
        logger.info(f"Starting update from {current_branch}@{current_commit}")
        
        # Fetch latest changes
        logger.info("Fetching latest changes from GitHub...")
        subprocess.run(
            ["git", "fetch", "origin"],
            capture_output=True,
            text=True,
            check=True,
            cwd=os.getcwd()
        )
        
        if target_version:
            # Checkout specific tag/version
            logger.info(f"Checking out version {target_version}...")
            subprocess.run(
                ["git", "checkout", f"tags/{target_version}"],
                capture_output=True,
                text=True,
                check=True,
                cwd=os.getcwd()
            )
            update_method = f"checkout {target_version}"
        else:
            # Pull latest from current branch
            logger.info(f"Pulling latest changes for {current_branch}...")
            subprocess.run(
                ["git", "pull", "origin", current_branch],
                capture_output=True,
                text=True,
                check=True,
                cwd=os.getcwd()
            )
            update_method = f"pull from {current_branch}"
        
        # Get new commit
        new_commit = await get_current_commit()
        
        # Check if there were any changes
        if current_commit == new_commit and not target_version:
            return {
                "success": True,
                "updated": False,
                "message": "Already up to date",
                "current_commit": current_commit,
                "new_commit": new_commit,
            }
        
        logger.info(f"Successfully updated from {current_commit} to {new_commit}")
        
        return {
            "success": True,
            "updated": True,
            "message": f"Successfully updated via {update_method}",
            "previous_commit": current_commit,
            "new_commit": new_commit,
            "method": update_method,
            "restart_required": True,
        }
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        logger.error(f"Update failed: {error_msg}")
        raise UpdateError(f"Git operation failed: {error_msg}")
    except Exception as e:
        logger.error(f"Unexpected error during update: {e}")
        raise UpdateError(f"Unexpected error: {str(e)}")


async def get_update_info() -> Dict[str, Any]:
    """
    Get comprehensive update information.
    
    Returns:
        Dict with current state and update availability
    """
    try:
        current_branch = await get_current_branch()
        current_commit = await get_current_commit()
        git_status = await check_git_status()
        update_check = await check_for_updates()
        
        return {
            "current_version": CURRENT_VERSION,
            "current_branch": current_branch,
            "current_commit": current_commit,
            "git_clean": git_status["clean"],
            "uncommitted_changes": git_status.get("uncommitted_changes", []),
            "update_available": update_check.get("update_available", False),
            "latest_version": update_check.get("latest_version"),
            "release_url": update_check.get("release_url"),
            "release_notes": update_check.get("release_notes"),
            "can_update": git_status["clean"],  # Can only update if working dir is clean
        }
    except Exception as e:
        logger.error(f"Error getting update info: {e}")
        raise UpdateError(f"Failed to get update info: {str(e)}")
