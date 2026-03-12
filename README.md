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

2. Apply database migrations:

```bash
alembic upgrade head
```

3. Ensure `.env` is present and points to port 8000:

```text
AUTH0_CALLBACK_URL=http://127.0.0.1:8000/callback
AUTH0_LOGOUT_URL=http://127.0.0.1:8000/
```

4. Start server:

```bash
python app.py
```

5. Open:

```text
http://127.0.0.1:8000/
```

## Background evaluation worker

Evaluation is queued in Redis and processed by a separate worker. Start Redis, then run:

```bash
python -m backend.app.workers.run_evaluation_worker
```

Optional `.env` overrides (defaults shown):

```text
REDIS_URL=redis://127.0.0.1:6379/0
EVAL_QUEUE_NAME=evaluation
EVAL_MAX_WORKERS=4
EVAL_JOB_TIMEOUT=900
EVAL_JOB_TTL=3600
EVAL_FAILURE_TTL=3600
EVAL_REQUEUE_ENABLED=true
EVAL_REQUEUE_INTERVAL_SECONDS=60
EVAL_REQUEUE_BATCH_SIZE=25
EVAL_REQUEUE_LOCK_TTL_SECONDS=55
EVAL_REQUEUE_MAX_ATTEMPTS=5
EVAL_REQUEUE_ATTEMPT_TTL_SECONDS=86400
OPENAI_EVAL_MAX_CONCURRENT=2
```

## Production session hardening

When `APP_ENV=production`, these are enforced:

```text
APP_ENV=production
SESSION_SECRET=use-a-long-random-secret
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=lax
SESSION_COOKIE_DOMAIN=yourdomain.com
```

## Worker supervision (systemd)

Sample unit files are in `deploy/systemd/`. Update the paths and user, then install:

```bash
sudo cp deploy/systemd/meetngreet-api.service /etc/systemd/system/
sudo cp deploy/systemd/meetngreet-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now meetngreet-api
sudo systemctl enable --now meetngreet-worker
```

The worker unit includes a `CPUQuota` limit; adjust it to fit your server capacity.

Optional env vars for launcher:

```text
APP_HOST=127.0.0.1
APP_PORT=8000
APP_RELOAD=true
```

The launcher already watches only `backend/app` to avoid reloads caused by media writes.

## Health checks

Optional `.env` overrides:

```text
HEALTHCHECK_OPENAI=false
HEALTHCHECK_OPENAI_TIMEOUT_SECONDS=5
RQ_FAILED_JOB_ALERT_THRESHOLD=10
```

## Tracing (OpenTelemetry)

Set these to enable tracing:

```text
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer%20token
```

## Load testing

K6 (requires a valid session cookie):

```bash
k6 run loadtest/k6/interview.js
```

Locust:

```bash
pip install -r loadtest/requirements.txt
locust -f loadtest/locust/locustfile.py -u 50 -r 10 -t 5m
```

Both scripts read:

```text
BASE_URL=http://127.0.0.1:8000
SESSION_COOKIE_NAME=meetngreet_session
SESSION_COOKIE=your_session_cookie_value
```
