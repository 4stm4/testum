# Application Updates

## Overview

Testum includes an automatic update system that checks for new releases on GitHub and allows you to update the application with a single click.

## Features

- ✅ Check for updates from GitHub releases
- ✅ View release notes before updating
- ✅ One-click update installation
- ✅ Git-based update mechanism
- ✅ Version comparison
- ✅ Safety checks (uncommitted changes detection)

## How It Works

### Update Flow

1. **Check for Updates**
   - Application queries GitHub API for latest release
   - Compares current version with latest version
   - Shows release notes and changelog
   - Checks if working directory is clean (no uncommitted changes)

2. **Install Update**
   - Performs `git fetch origin`
   - Pulls latest changes from GitHub
   - Updates application code in-place
   - Notifies you to restart the application

3. **Restart Application**
   - You manually restart the Docker container
   - Application loads with new code

### Version Information

The system tracks:
- **Current Version**: Semantic version (e.g., v0.1.0)
- **Current Branch**: Git branch (e.g., main)
- **Current Commit**: Short commit hash (e.g., abc1234)
- **Latest Version**: Latest release on GitHub
- **Release Notes**: Changelog for new version

## Usage

### Via Settings Page

1. **Navigate to Settings**
   - Go to Settings page in the UI
   - Scroll to "Application Updates" section

2. **Check for Updates**
   - Click "🔍 Check for Updates" button
   - View current version information
   - See if updates are available

3. **Install Update** (if available)
   - Click "⬇️ Install Update" button
   - Confirm the action
   - Wait for update to complete

4. **Restart Application**
   ```bash
   docker-compose restart
   # or
   docker-compose up -d --build
   ```

### Via API

**Check for Updates:**
```bash
curl -X GET http://localhost:8000/api/updates/check \
  -H "Cookie: access_token=YOUR_JWT_TOKEN"
```

Response:
```json
{
  "current_version": "0.1.0",
  "current_branch": "main",
  "current_commit": "abc1234",
  "git_clean": true,
  "uncommitted_changes": [],
  "update_available": true,
  "latest_version": "0.2.0",
  "release_url": "https://github.com/4stm4/testum/releases/tag/v0.2.0",
  "release_notes": "## What's New\n- Feature 1\n- Feature 2",
  "can_update": true
}
```

**Perform Update:**
```bash
curl -X POST http://localhost:8000/api/updates/perform \
  -H "Cookie: access_token=YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Response:
```json
{
  "success": true,
  "updated": true,
  "message": "Successfully updated via pull from main",
  "previous_commit": "abc1234",
  "new_commit": "def5678",
  "method": "pull from main",
  "restart_required": true
}
```

## Configuration

### GitHub Repository

Edit `app/updater.py` to change the repository:

```python
# GitHub repository
GITHUB_OWNER = "4stm4"
GITHUB_REPO = "testum"
```

### Current Version

Update version in `app/updater.py`:

```python
# Current version
CURRENT_VERSION = "0.1.0"
```

**Important:** Keep this in sync with your releases!

## Safety Features

### Uncommitted Changes Detection

The updater checks for uncommitted changes before updating:

```python
# Check git status
git status --porcelain
```

If there are uncommitted changes, the update is **blocked** to prevent data loss.

**To proceed:**
1. Commit your changes: `git commit -am "Your message"`
2. Or stash them: `git stash`
3. Then run the update again

### Working Directory Check

Before updating, the system verifies:
- ✅ Git repository is initialized
- ✅ No uncommitted changes
- ✅ No untracked files that would be overwritten
- ✅ Remote repository is accessible

## Creating Releases

### On GitHub

1. **Create a new release**
   - Go to your repository on GitHub
   - Click "Releases" → "Create a new release"

2. **Tag version**
   - Use semantic versioning: `v0.2.0`, `v1.0.0`, etc.
   - Tag format: `v` prefix + version number

3. **Write release notes**
   - Describe new features
   - List bug fixes
   - Mention breaking changes

4. **Publish release**
   - Click "Publish release"
   - Application will detect it on next check

### Example Release Notes

```markdown
## What's New in v0.2.0

### Features
- 🌍 Added language switcher (EN/RU)
- 🎨 Added theme switcher (Dark/Light)
- 🔄 Added automatic update system

### Improvements
- ⚡ Faster SSH connection handling
- 🔒 Enhanced security for password storage

### Bug Fixes
- 🐛 Fixed task monitoring WebSocket reconnection
- 🐛 Fixed settings page layout on mobile

### Breaking Changes
- None

### Migration Guide
- No migration required
- Simply pull the latest code and restart
```

## Update Process Details

### Git Operations

The updater performs these git commands:

1. **Fetch latest changes:**
   ```bash
   git fetch origin
   ```

2. **Pull from current branch:**
   ```bash
   git pull origin main
   ```

3. **Or checkout specific tag:**
   ```bash
   git checkout tags/v0.2.0
   ```

### Docker Restart

After updating, restart the container:

**Option 1: Quick restart**
```bash
docker-compose restart
```
- Fast (2-5 seconds)
- Keeps current container
- Reloads application code

**Option 2: Full rebuild**
```bash
docker-compose up -d --build
```
- Slower (1-2 minutes)
- Rebuilds Docker image
- Installs new dependencies if `requirements.txt` changed

**When to use each:**
- Use **restart** for code-only changes
- Use **rebuild** when `requirements.txt` or `Dockerfile` changed

## Troubleshooting

### "Update available" but button disabled

**Problem:** Update is available but "Install Update" button is disabled

**Cause:** Uncommitted changes in working directory

**Solution:**
```bash
# Check what changed
git status

# Commit changes
git add .
git commit -m "My changes"

# Or stash changes
git stash

# Try update again
```

### "Failed to check for updates"

**Problem:** Cannot connect to GitHub API

**Causes:**
- No internet connection
- GitHub API rate limit exceeded (60 requests/hour for unauthenticated)
- Repository is private

**Solutions:**
1. Check internet connection
2. Wait an hour for rate limit to reset
3. Make repository public or add GitHub token

### "Git operation failed"

**Problem:** Update fails with git error

**Common causes:**
1. **Merge conflicts**
   ```bash
   # View conflicts
   git status
   
   # Resolve conflicts manually or reset
   git reset --hard origin/main
   ```

2. **Detached HEAD state**
   ```bash
   # Return to main branch
   git checkout main
   git pull origin main
   ```

3. **No remote configured**
   ```bash
   # Add remote
   git remote add origin https://github.com/4stm4/testum.git
   ```

### Update completed but changes not visible

**Problem:** Updated successfully but application still shows old version

**Cause:** Container not restarted

**Solution:**
```bash
# Restart container
docker-compose restart

# Or rebuild if dependencies changed
docker-compose up -d --build
```

## API Errors

### Error Responses

**401 Unauthorized:**
```json
{
  "error": "Unauthorized"
}
```
- You're not logged in
- JWT token expired
- Solution: Log in again

**400 Bad Request:**
```json
{
  "error": "Working directory has uncommitted changes. Please commit or stash them first."
}
```
- Uncommitted changes detected
- Solution: Commit or stash changes

**500 Internal Server Error:**
```json
{
  "error": "Failed to check for updates: HTTP error 403"
}
```
- GitHub API rate limit exceeded
- Network error
- Solution: Wait and retry

## Best Practices

### Before Updating

1. ✅ **Backup your data**
   - Export important SSH keys
   - Backup platform configurations
   - Save `.env` file

2. ✅ **Check release notes**
   - Read breaking changes
   - Understand new features
   - Review migration guide

3. ✅ **Ensure clean working directory**
   - Commit or stash changes
   - No untracked files

4. ✅ **Schedule maintenance window**
   - Update during low-traffic period
   - Inform users about downtime

### After Updating

1. ✅ **Restart application**
   ```bash
   docker-compose restart
   ```

2. ✅ **Verify functionality**
   - Test login
   - Check SSH key operations
   - Verify platform connectivity

3. ✅ **Check logs**
   ```bash
   docker-compose logs -f app
   ```

4. ✅ **Monitor health**
   - Visit `/health` endpoint
   - Check system resources

### Rollback Plan

If update causes issues:

1. **View commit history:**
   ```bash
   git log --oneline
   ```

2. **Rollback to previous version:**
   ```bash
   git checkout <previous-commit-hash>
   docker-compose restart
   ```

3. **Or checkout previous release:**
   ```bash
   git checkout tags/v0.1.0
   docker-compose restart
   ```

## Advanced Usage

### Update to Specific Version

Via API:
```bash
curl -X POST http://localhost:8000/api/updates/perform \
  -H "Cookie: access_token=YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_version": "v0.2.0"}'
```

This will checkout the specific tag `v0.2.0` instead of pulling latest from branch.

### Automated Updates

Create a cron job to check for updates daily:

```bash
# Add to crontab
0 2 * * * curl -X GET http://localhost:8000/api/updates/check >> /var/log/testum-updates.log 2>&1
```

**Warning:** Don't automate the actual update installation - always review release notes first!

### Custom Update Script

Create a shell script for automated updates:

```bash
#!/bin/bash
# update-testum.sh

echo "Checking for Testum updates..."

# Check for updates
RESPONSE=$(curl -s http://localhost:8000/api/updates/check)
UPDATE_AVAILABLE=$(echo $RESPONSE | jq -r '.update_available')

if [ "$UPDATE_AVAILABLE" = "true" ]; then
    echo "Update available!"
    LATEST=$(echo $RESPONSE | jq -r '.latest_version')
    echo "Latest version: $LATEST"
    
    # Perform update
    echo "Installing update..."
    curl -X POST http://localhost:8000/api/updates/perform \
      -H "Content-Type: application/json" \
      -d '{}'
    
    # Restart application
    echo "Restarting application..."
    docker-compose restart
    
    echo "Update completed!"
else
    echo "Already up to date."
fi
```

## Security Considerations

### Authentication Required

All update endpoints require authentication:
- Must be logged in with valid JWT token
- Only administrators can perform updates

### Rate Limiting

GitHub API has rate limits:
- **Unauthenticated:** 60 requests/hour
- **Authenticated:** 5000 requests/hour

To use authenticated requests, add GitHub token:

```python
# In app/updater.py
response = await client.get(
    url,
    headers={
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
)
```

### Private Repositories

For private repositories:
1. Generate GitHub Personal Access Token (PAT)
2. Add to environment variables: `GITHUB_TOKEN`
3. Update `app/updater.py` to use token in API requests

## Monitoring

### Update Logs

Updates are logged:

```bash
# View update logs
docker-compose logs app | grep -i update
```

Example log output:
```
[2025-11-09 12:00:00] INFO: Starting update from main@abc1234
[2025-11-09 12:00:01] INFO: Fetching latest changes from GitHub...
[2025-11-09 12:00:03] INFO: Pulling latest changes for main...
[2025-11-09 12:00:05] INFO: Successfully updated from abc1234 to def5678
```

### Health Monitoring

Check application health after update:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-09T12:00:00.000000"
}
```

## Future Enhancements

Planned features:

- [ ] Automatic update scheduling
- [ ] Update rollback from UI
- [ ] Update history/changelog viewer
- [ ] Email notifications for new releases
- [ ] Update diff viewer (show changed files)
- [ ] Pre-update health checks
- [ ] Post-update smoke tests
- [ ] Multi-environment support (dev/staging/prod)

---

**Version:** 0.1.0  
**Last Updated:** 9 ноября 2025 г.
