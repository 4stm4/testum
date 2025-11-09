# Update System UI Preview

## Settings Page - Updates Section

```
┌─────────────────────────────────────────────────────────────────┐
│  🔄 Application Updates                                         │
│                                                                 │
│  Check for and install updates from GitHub                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Current Version                                                │
│  ┌─────────────────┐                                           │
│  │ 0.1.0           │                                           │
│  └─────────────────┘                                           │
│                                                                 │
│  Current Branch                                                 │
│  ┌─────────────────┐                                           │
│  │ main            │                                           │
│  └─────────────────┘                                           │
│                                                                 │
│  Current Commit                                                 │
│  ┌─────────────────┐                                           │
│  │ abc1234         │                                           │
│  └─────────────────┘                                           │
│                                                                 │
│  Latest Version Available                                       │
│  ┌─────────────────┐                                           │
│  │ v0.2.0 🎉       │  (green)                                  │
│  └─────────────────┘                                           │
│                                                                 │
│  Release Notes                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ## What's New in v0.2.0                                 │   │
│  │                                                         │   │
│  │ ### Features                                            │   │
│  │ - 🔄 Added automatic update system                      │   │
│  │ - 🌍 Added language switcher (EN/RU)                    │   │
│  │ - 🎨 Added theme switcher (Dark/Light)                  │   │
│  │                                                         │   │
│  │ ### Improvements                                        │   │
│  │ - ⚡ Faster SSH connection handling                     │   │
│  │ - 🔒 Enhanced security                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐                     │
│  │ 🔍 Check for    │  │ ⬇️ Install      │  ✅ Update available!│
│  │    Updates      │  │    Update       │  (green text)       │
│  └─────────────────┘  └─────────────────┘                     │
│                                                                 │
│  ⚠️ Warning: After updating, you will need to restart the     │
│     application manually using docker-compose restart          │
├─────────────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────────┘
```

## User Flow

### Step 1: Check for Updates
```
User clicks: "🔍 Check for Updates"

↓

Button changes to: "🔄 Checking..."

↓

API call: GET /api/updates/check

↓

Response received:
{
  "update_available": true,
  "current_version": "0.1.0",
  "latest_version": "0.2.0",
  "release_notes": "## What's New...",
  "can_update": true
}

↓

UI updates:
- Shows version info
- Shows release notes
- Shows "⬇️ Install Update" button
- Status: "✅ Update available!" (green)
```

### Step 2: Install Update
```
User clicks: "⬇️ Install Update"

↓

Confirmation dialog:
"Are you sure you want to update the application?
You will need to restart the container after the update."

↓

User confirms

↓

Button changes to: "⬇️ Updating..."
Status: "Downloading updates..." (blue)

↓

API call: POST /api/updates/perform

↓

Git operations:
1. git fetch origin
2. git pull origin main

↓

Response received:
{
  "success": true,
  "updated": true,
  "message": "Successfully updated via pull from main",
  "previous_commit": "abc1234",
  "new_commit": "def5678",
  "restart_required": true
}

↓

Success message displayed:
"✅ Successfully updated via pull from main

Previous commit: abc1234
New commit: def5678

⚠️ Please restart the application:
docker-compose restart or docker-compose up -d --build"

↓

Button hidden
Status: "✅ Update downloaded! Restart required." (green)
```

### Step 3: Restart Application
```
User runs in terminal:

$ docker-compose restart

or

$ docker-compose up -d --build

↓

Application reloads with new code

↓

User refreshes browser

↓

New version is active! 🎉
```

## Error States

### Uncommitted Changes
```
┌─────────────────────────────────────────────────────────────────┐
│  Status: ⚠️ Cannot update: uncommitted changes (orange)        │
│                                                                 │
│  ⚠️ Warning message:                                           │
│  Your working directory has uncommitted changes.               │
│  Please commit or stash them before updating.                  │
│                                                                 │
│  "⬇️ Install Update" button is DISABLED                        │
└─────────────────────────────────────────────────────────────────┘
```

### No Updates Available
```
┌─────────────────────────────────────────────────────────────────┐
│  Current Version: 0.1.0                                         │
│  Current Branch: main                                           │
│  Current Commit: abc1234                                        │
│                                                                 │
│  Status: ✅ You are up to date! (green)                        │
│                                                                 │
│  "⬇️ Install Update" button is HIDDEN                          │
└─────────────────────────────────────────────────────────────────┘
```

### Update Failed
```
┌─────────────────────────────────────────────────────────────────┐
│  ❌ Error message:                                              │
│  Update failed: Git operation failed: merge conflict            │
│                                                                 │
│  Status: ❌ Update failed (red)                                │
│                                                                 │
│  Buttons return to normal state                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Color Scheme

### Dark Theme (Default)
- Background: `#181825`
- Text: `#cdd6f4`
- Current values: `#313244` background, `#89b4fa` text
- Buttons: `#89b4fa` background, `#1e1e2e` text
- Success: `#a6e3a1` (green)
- Warning: `#fab387` (orange)
- Error: `#f38ba8` (red)
- Info: `#89b4fa` (blue)

### Light Theme
- Background: `#f5f7fa`
- Text: `#1f2937`
- Current values: `#e5e7eb` background, `#3b82f6` text
- Buttons: `#3b82f6` background, `#ffffff` text
- Success: `#10b981` (green)
- Warning: `#f59e0b` (orange)
- Error: `#ef4444` (red)
- Info: `#3b82f6` (blue)

## Responsive Behavior

### Desktop (> 768px)
```
┌──────────────────────────────────────────────────┐
│  [Check] [Install] Status text here...          │
└──────────────────────────────────────────────────┘
```

### Mobile (< 768px)
```
┌─────────────────┐
│  [Check Update] │
├─────────────────┤
│  [Install]      │
├─────────────────┤
│  Status text    │
│  here...        │
└─────────────────┘
```

## JavaScript Events

```javascript
// Check button clicked
checkUpdatesBtn.onclick = checkForUpdates()

// Install button clicked
performUpdateBtn.onclick = performUpdate()

// Auto-check on page load (optional)
window.addEventListener('DOMContentLoaded', () => {
    // Could auto-check here
});
```

## API Integration

### Check Endpoint
```http
GET /api/updates/check
Authorization: Cookie access_token=<jwt>

Response 200:
{
  "current_version": "0.1.0",
  "current_branch": "main",
  "current_commit": "abc1234",
  "git_clean": true,
  "uncommitted_changes": [],
  "update_available": true,
  "latest_version": "0.2.0",
  "release_url": "https://github.com/4stm4/testum/releases/tag/v0.2.0",
  "release_notes": "## What's New\n...",
  "can_update": true
}
```

### Perform Endpoint
```http
POST /api/updates/perform
Authorization: Cookie access_token=<jwt>
Content-Type: application/json

{}

Response 200:
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

## Security

- ✅ Requires authentication (JWT token)
- ✅ Only admin users can check/perform updates
- ✅ Git operations run with user permissions
- ✅ No arbitrary code execution
- ✅ Working directory safety checks

## Future Enhancements

- [ ] Auto-check on page load
- [ ] Periodic background checks
- [ ] Notification when update available
- [ ] Update history viewer
- [ ] Rollback functionality from UI
- [ ] Update scheduling
