# LED Wall Designer with Authentication

Production-grade LED wall design application with MongoDB-based authentication and user project management.

## Features

✅ **User Authentication** - Secure registration and login with Argon2id password hashing  
✅ **Project Ownership** - Each user has their own private projects  
✅ **Role-Based Access** - User and Admin roles with permission enforcement  
✅ **Admin Dashboard** - View all users and projects with owner information  
✅ **Secure Sessions** - JWT access tokens + refresh token rotation  
✅ **Rate Limiting** - Protection against brute force attacks  
✅ **MongoDB Storage** - Scalable NoSQL database for users and projects

---

## Quick Start

### 1. Prerequisites

- Python 3.8+
- MongoDB 4.4+ (running locally or remote)

### 2. Install MongoDB

**Windows:**
```powershell
# Download from: https://www.mongodb.com/try/download/community
# Or use Chocolatey:
choco install mongodb
```

**Start MongoDB:**
```powershell
# If installed as service, it auto-starts
# Or run manually:
mongod --dbpath C:\data\db
```

### 3. Install Dependencies

```powershell
cd av_wall_designer
python -m pip install -r requirements.txt
```

### 4. Configure Environment

```powershell
# Copy template
Copy-Item .env.example .env

# Generate secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Edit .env and set:
# - SECRET_KEY=<generated-key>
# - MONGODB_URI=mongodb://localhost:27017/  (or your MongoDB URI)
```

### 5. Create First Admin

```powershell
# Interactive
python setup_admin.py

# Or with arguments
python setup_admin.py "admin@example.com" "SecurePass123!" "Admin Name"

# Or with environment variables
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="SecurePass123!"
$env:ADMIN_NAME="Admin User"
python setup_admin.py
```

### 6. Start Application

```powershell
python app.py
```

Access at: **http://127.0.0.1:5000**

---

## API Usage

### Register

```http
POST /api/auth/register
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "SecurePass123",
    "name": "John Doe"
}
```

### Login

```http
POST /api/auth/login
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "SecurePass123"
}
```

Returns `access_token` and sets `refresh_token` cookie.

### Use API

Add token to all protected requests:

```http
GET /api/projects
Authorization: Bearer <access_token>
```

### Refresh Token

```http
POST /api/auth/refresh
```

Uses HttpOnly cookie, returns new access token.

---

## Project Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects` | List user's projects |
| GET | `/api/projects/:id` | Get project (owner only) |
| POST | `/api/projects` | Create project |
| PUT | `/api/projects/:id` | Update project (owner only) |
| DELETE | `/api/projects/:id` | Delete project (owner only) |

---

## Admin Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/dashboard` | Statistics |
| GET | `/api/admin/users` | All users |
| GET | `/api/admin/projects` | All projects with owners |

---

## Security Features

- ✅ Argon2id password hashing
- ✅ JWT access tokens (15-min expiry)
- ✅ Refresh token rotation (30-day expiry)
- ✅ HttpOnly cookies (XSS protection)
- ✅ SameSite cookies (CSRF protection)
- ✅ Rate limiting (5 login attempts/min)
- ✅ Backend ownership verification
- ✅ Role-based authorization

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URI` | `mongodb://localhost:27017/` | MongoDB connection string |
| `MONGODB_DB_NAME` | `led_wall_designer` | Database name |
| `SECRET_KEY` | *(required)* | JWT signing key |
| `FLASK_ENV` | `development` | Environment mode |
| `SESSION_COOKIE_SECURE` | `False` | HTTPS-only cookies (production) |
| `ACCESS_TOKEN_EXPIRY` | `900` | Access token lifetime (seconds) |
| `REFRESH_TOKEN_EXPIRY` | `2592000` | Refresh token lifetime (seconds) |

---

## Production Deployment

### 1. Set Production Config

```ini
# .env
SECRET_KEY=<strong-random-key>
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGODB_DB_NAME=led_wall_designer_prod
FLASK_ENV=production
SESSION_COOKIE_SECURE=True
```

### 2. Enable HTTPS

Use a reverse proxy (nginx/Apache) or deploy with gunicorn + TLS.

### 3. Create Admin

```powershell
python setup_admin.py
```

### 4. Start Application

```powershell
python app.py
```

---

## MongoDB Collections

### users
```javascript
{
    _id: ObjectId,
    email: String (unique, indexed),
    password_hash: String,
    name: String,
    role: String ("user" | "admin"),
    created_at: DateTime,
    updated_at: DateTime
}
```

### sessions
```javascript
{
    _id: ObjectId,
    user_id: String (indexed),
    token_hash: String (unique, indexed),
    expires_at: DateTime (indexed),
    created_at: DateTime
}
```

### projects
```javascript
{
    _id: ObjectId,
    user_id: String (indexed),
    name: String,
    payload: Object (design data),
    created_at: DateTime,
    updated_at: DateTime (indexed)
}
```

---

## Troubleshooting

### "Cannot connect to MongoDB"
```powershell
# Check MongoDB is running
mongo --eval "db.version()"

# Or use MongoDB Compass to test connection
```

### "SECRET_KEY must be set"
```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Add output to .env file
```

### "An administrator already exists"
Only one admin via setup script. Create more via MongoDB:
```javascript
db.users.updateOne(
    {email: "new-admin@example.com"},
    {$set: {role: "admin"}}
)
```

---

## Development

### Run Tests

```powershell
python -m unittest discover -s tests
```

### MongoDB Shell

```powershell
# Connect
mongo

# Use database
use led_wall_designer

# View users
db.users.find().pretty()

# View projects
db.projects.find().pretty()
```

---

## License

Internal company project.

---

**Version**: 2.0 (MongoDB)  
**Last Updated**: October 23, 2026
