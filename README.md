# MeetnGreet Automation System
AI - Driven smart automation system for the initial round of the selection process.
This project is an interview automation system with:
- FastAPI backend
- HTML/CSS/JS frontend
- MySQL-ready persistence
- Candidate login via Auth0 SSO (Google/Microsoft)
- AI-based transcript + evaluation flow

## Current login flow

1. Open `http://127.0.0.1:8000/`
2. Candidate signs in with:
   - Google SSO (Auth0)
   - Microsoft SSO (Auth0)
3. On success, user is redirected to `/interview`
4. Candidate starts interview without entering candidate id manually

## Database

By default, the app now uses a local SQLite database for all interview/auth tables.

Set this in `.env` (optional, defaults shown):

```text
USE_LOCAL_DB=true
LOCAL_DB_PATH=./backend/storage/local_app.db
```

If you want MySQL instead, set:

```text
USE_LOCAL_DB=false
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=auth_system
```

Optional:

```text
DATABASE_URL=mysql+pymysql://root:your_password@127.0.0.1:3306/auth_system
```

`users` table fields used:
- `id`
- `unique_id`
- `email`
- `provider`
- `created_at`

## Auth0 config

Set these in `.env`:

```text
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your_client_id
AUTH0_CLIENT_SECRET=your_client_secret
AUTH0_CALLBACK_URL=http://127.0.0.1:8000/callback
AUTH0_LOGOUT_URL=http://127.0.0.1:8000/
AUTH0_GOOGLE_CONNECTION=google-oauth2
AUTH0_MICROSOFT_CONNECTION=windowslive
```

In Auth0 dashboard, allow:
- Callback URL: `http://127.0.0.1:8000/callback`
- Logout URL: `http://127.0.0.1:8000/`
- Web Origin: `http://127.0.0.1:8000`

## Run

1. Install dependencies:

```bash
pip install -r backend/requirements.txt
```

2. Ensure `.env` is present and points to port 8000:

```text
AUTH0_CALLBACK_URL=http://127.0.0.1:8000/callback
AUTH0_LOGOUT_URL=http://127.0.0.1:8000/
```

3. Start server:

```bash
python app.py
```

4. Open:

```text
http://127.0.0.1:8000/
```

Optional env vars for launcher:

```text
APP_HOST=127.0.0.1
APP_PORT=8000
APP_RELOAD=true
```

The launcher already watches only `backend/app` to avoid reloads caused by media writes.
