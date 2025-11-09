# Authentication System

## Overview

Testum now includes a complete authentication system based on JWT tokens stored in HTTP-only cookies.

## Features

### 🔐 Login System
- Beautiful dark-themed login page at `/login`
- JWT token-based authentication
- Secure cookie storage (24-hour expiration)
- Auto-redirect if already authenticated

### 🛡️ Protected Routes
All routes except the following require authentication:
- `/login` - Login page
- `/api/auth/login` - Login API endpoint
- `/health` - Health check
- `/docs` - API documentation

### 🚪 Logout
- Logout button in header of all pages
- Clears authentication cookie
- Redirects to login page

## Default Credentials

```
Username: admin
Password: admin123
```

**⚠️ IMPORTANT:** Change these credentials in production!

## Configuration

Credentials are configured via environment variables:

```bash
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
SECRET_KEY=your-secret-key-here
```

## Technical Details

### Authentication Flow

1. User visits any page
2. `AuthMiddleware` checks for `access_token` cookie
3. If no token or invalid token → redirect to `/login`
4. User submits credentials to `/api/auth/login`
5. Server validates and returns JWT token
6. JavaScript stores token in cookie
7. Subsequent requests include cookie automatically

### JWT Token

- Algorithm: HS256
- Expiration: 24 hours
- Claims:
  - `sub`: username
  - `exp`: expiration timestamp
  - `iat`: issued at timestamp

### Middleware Behavior

**For HTML pages:**
- No auth → Redirect to `/login` (302)
- Invalid token → Redirect to `/login` + clear cookie

**For API endpoints:**
- No auth → 401 JSON error
- Invalid token → 401 JSON error

## Security Notes

### Current Implementation (MVP)
- Single hardcoded admin user
- Password stored in environment variable (plain text)
- Simple credential check

### Future Improvements (v0.2.0)
A migration file `003_add_users_table.py` is already prepared for:
- Multiple users support
- Hashed passwords (bcrypt)
- User roles and permissions
- Email support
- Last login tracking

To enable multi-user support:
1. Run migration: `alembic upgrade head`
2. Update `app/models.py` with User model
3. Update `app/auth.py` with password hashing
4. Update `app/main.py` to check database

## API Endpoints

### POST /api/auth/login
Login endpoint.

**Request:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

**Response (401):**
```json
{
  "error": "Invalid credentials"
}
```

### GET /api/auth/logout
Logout endpoint (also accepts POST).

**Response:**
- Redirect to `/login` with cookie cleared

## UI Components

### Login Page
- Centered card design
- Dark theme matching Portainer style
- Auto-focus on username field
- Loading state during submission
- Error message display

### Logout Button
- Present in header of all authenticated pages
- Red/pink color scheme
- Door emoji icon
- Hover animation

## Testing

### Manual Testing
1. Visit `http://localhost:8000/`
2. Should redirect to `/login`
3. Enter `admin` / `admin123`
4. Should redirect to dashboard
5. Click "Logout" button
6. Should clear session and return to login

### Verify Protection
```bash
# Without auth - should get 401
curl -X GET http://localhost:8000/api/keys

# With auth cookie - should work
curl -X GET http://localhost:8000/api/keys \
  --cookie "access_token=YOUR_TOKEN_HERE"
```

## File Structure

```
app/
├── auth.py              # AuthMiddleware + JWT utilities
├── main.py              # Login/logout endpoints + middleware setup
└── templates/
    ├── login.html       # Login page
    ├── index.html       # Dashboard (with logout button)
    ├── keys.html        # Keys page (with logout button)
    ├── platforms.html   # Platforms page (with logout button)
    └── task.html        # Task page (with logout button)

migrations/versions/
└── 003_add_users_table.py  # Future multi-user support
```

## Troubleshooting

### Can't login with admin/admin123
Check environment variables:
```bash
docker-compose exec app env | grep ADMIN
```

### Keep getting redirected to login
Check if JWT secret key is consistent:
```bash
docker-compose exec app env | grep SECRET_KEY
```

Token signed with one key won't validate with another.

### Logout doesn't work
Check browser cookies:
- Open DevTools → Application → Cookies
- Verify `access_token` is deleted after logout

## Next Steps

For production deployment:

1. **Change default credentials:**
   ```yaml
   environment:
     - ADMIN_USERNAME=your_username
     - ADMIN_PASSWORD=your_secure_password
   ```

2. **Generate strong SECRET_KEY:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. **Enable HTTPS:**
   - Use reverse proxy (nginx/traefik)
   - Set `Secure` flag on cookies

4. **Consider multi-user support:**
   - Run migration 003
   - Implement user management UI
   - Add password hashing
