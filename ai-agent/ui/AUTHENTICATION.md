# Bot MVP - Authentication System

## Overview

This deployment package includes a complete authentication system with two layers:
1. **Web Server Authentication** - Session-based cookies (30-day expiration)
2. **API Server Authentication** - Bearer token-based access

Both use MD5 password hashing stored in `.env` file.

---

## Configuration

### Password Setup

Edit `.env` file to set your password:

```bash
# First, generate MD5 hash of your password
# Linux/Mac: echo -n "your_password" | md5sum
# Windows: certutil -hashfile "your_file" MD5  (or use online MD5 tool)

# Then add to .env:
AUTH_PASSWORD_MD5=<your_md5_hash_here>
AUTH_COOKIE_DAYS=30  # Web session cookie expiry
```

**Example:**
- Password: `qqqppp686868`
- MD5 Hash: `081904e6952d21450814cd3c465cf059`

```env
AUTH_PASSWORD_MD5=081904e6952d21450814cd3c465cf059
AUTH_COOKIE_DAYS=30
```

---

## Web Server Authentication (Port 8080)

### Login Flow

1. **User visits** `http://localhost:8080`
2. **Login page** appears with password form
3. **User enters password** and clicks "Login"
4. **Frontend** calls `/login` endpoint on **API server** (port 8100) to get token
5. **Frontend** saves token to `localStorage`
6. **Frontend** calls `/auth` endpoint on **Web server** to set session cookie
7. **Server** sets `bot_mvp_auth` cookie with 30-day expiration
8. **User** redirected to `/index.html`

### Session Management

- **Cookie Name:** `bot_mvp_auth`
- **Cookie Expiry:** 30 days (configurable via `AUTH_COOKIE_DAYS`)
- **Security:** HttpOnly, SameSite=Lax
- **Persistence:** "Remember me" checkbox saves 30-day cookie

### Protected Routes

- `/index.html` - Main chat interface
- `/stats.html` - Statistics page
- `/messages.html` - Message history
- `/settings.html` - Settings page
- `/admin.html` - Admin panel

### Public Routes

- `/login.html` - Login page
- `/` - Redirects to login page
- `/auth` - Login form submission endpoint

---

## API Server Authentication (Port 8100)

### Token Retrieval

```bash
curl -X POST http://localhost:8100/login \
  -H "Content-Type: application/json" \
  -d '{"password":"qqqppp686868"}'

# Response:
# {"token":"081904e6952d21450814cd3c465cf059","message":"Login successful"}
```

### Using the Token

Include token in API requests using **Authorization header**:

```bash
curl http://localhost:8100/chat \
  -H "Authorization: Bearer 081904e6952d21450814cd3c465cf059" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","user_id":1}'
```

**Alternative:** Query parameter

```bash
curl "http://localhost:8100/chat?token=081904e6952d21450814cd3c465cf059" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","user_id":1}'
```

### Public API Endpoints

- `GET /health` - Health check (no auth required)
- `POST /login` - Get authentication token (no auth required)
- `GET /docs` - API documentation (no auth required)
- `GET /openapi.json` - OpenAPI schema (no auth required)

### Protected API Endpoints

All other endpoints require `Authorization: Bearer <token>` header:

- `POST /chat` - Send message to bot
- `GET /conversations/<id>` - Get conversation
- `GET /messages/user/<user_id>` - Get user messages
- `GET /stats` - Get usage statistics
- `POST /users/` - Create user
- `POST /roles/` - Create role
- And more...

---

## Frontend Integration (index.html)

### Token Management

```javascript
// Get stored token
const token = localStorage.getItem('bot_api_token');

// Helper function to add auth headers
function getAuthHeaders() {
  const token = localStorage.getItem('bot_api_token') || '';
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

// Make authenticated API call
fetch('http://localhost:8100/chat', {
  method: 'POST',
  headers: getAuthHeaders(),
  body: JSON.stringify({ message: "Hello" })
})
```

### Login Form (web_server.py)

The login form automatically:
1. Gets API token from `POST /login`
2. Saves token to localStorage
3. Sets web session cookie via `POST /auth`
4. Redirects to chat interface

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser/Client                     │
├─────────────────────────────────────────────────────┤
│  login.html → POST /auth → set cookie               │
│  index.html → GET (check cookie) → serve            │
│             → fetch() with Authorization header      │
└──────────────────────────────────────────────────────┘
         │                                    │
      Cookie                            Bearer Token
         │                                    │
         ▼                                    ▼
┌──────────────────┐                ┌──────────────────────┐
│  Web Server      │                │  API Server          │
│  Port 8080       │                │  Port 8100 (FastAPI) │
├──────────────────┤                ├──────────────────────┤
│ ✓ /login.html    │                │ ✓ /login (POST)      │
│ ✓ /               │                │ ✓ /health (GET)      │
│ ✓ /auth (POST)   │                │ ✓ /docs (GET)        │
│ ✓ /index.html    │                │                      │
│ ✓ /stats.html    │                │ 🔐 /chat (POST)      │
│ 🔐 All other     │                │ 🔐 /stats (GET)      │
└──────────────────┘                │ 🔐 More endpoints    │
         │                          └──────────────────────┘
         │                                    │
         └─────────────────────────────────────┘
            MD5 password verification
            (from .env AUTH_PASSWORD_MD5)
```

---

## Security Features

✅ **MD5 Password Hashing** - Passwords stored as MD5 hashes in `.env`
✅ **Bearer Tokens** - Stateless API authentication
✅ **Session Cookies** - Stateful web interface authentication
✅ **HttpOnly Cookies** - Cannot be accessed via JavaScript (XSS protection)
✅ **SameSite=Lax** - CSRF protection
✅ **30-Day Expiration** - Session timeout on web interface
✅ **Environment Variables** - Secrets not hardcoded

---

## Troubleshooting

### "Invalid password" at login

- Verify `.env` has correct `AUTH_PASSWORD_MD5`
- Check password MD5 hash matches your intended password
- Generate new hash and update `.env`

### "API error: 401" when chatting

- Token not stored in localStorage
- Token expired or incorrect
- Check browser console: `localStorage.getItem('bot_api_token')`
- Re-login to get fresh token

### Cookie not persisting

- Check "Remember me" checkbox is checked
- Verify `AUTH_COOKIE_DAYS` is set in `.env`
- Check browser allows cookies for localhost

### CORS errors

- Web server runs on 8080, API on 8100 (different ports)
- API has CORS headers configured
- Token should be in Authorization header, not in OPTIONS requests

---

## Files Involved

| File | Purpose |
|------|---------|
| `auth.py` | Password hashing & verification utilities |
| `api.py` | FastAPI server with AuthMiddleware + /login endpoint |
| `web_server.py` | HTTP server with login page + session cookies |
| `.env` | Configuration (AUTH_PASSWORD_MD5, AUTH_COOKIE_DAYS) |
| `web/index.html` | Chat interface with API token support |
| `web_server.py` | Web server handling /auth & /login.html |

---

## Quick Start

1. **Update .env** with your MD5 password hash
2. **Run API server** (port 8100):
   ```bash
   python api.py
   ```
3. **Run Web server** (port 8080):
   ```bash
   python web_server.py
   ```
4. **Visit** `http://localhost:8080`
5. **Login** with password
6. **Chat** with bot!

---

## Password Generation Examples

### Linux/Mac
```bash
echo -n "mypassword123" | md5sum
# Output: 1e8662824e0b5e13e47e68e5b73e52e0
```

### Windows (PowerShell)
```powershell
(Get-FileHash -Path 'C:\temp\file.txt' -Algorithm MD5).Hash
# Or use online tool: https://www.tools.kmime.com/md5-hash-generator
```

### Python
```python
import hashlib
password = "mypassword123"
md5_hash = hashlib.md5(password.encode()).hexdigest()
print(md5_hash)  # 1e8662824e0b5e13e47e68e5b73e52e0
```
