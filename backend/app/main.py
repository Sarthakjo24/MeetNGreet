from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .config import settings
from .database import Base, engine
from .routers.auth import router as auth_router
from .routers.interview import router as interview_router


app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(interview_router)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

APP_BUILD_FINGERPRINT = "tw3-8000"
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-MeetnGreet-Build": APP_BUILD_FINGERPRINT,
}


@app.on_event("startup")
def on_startup() -> None:
    Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.evaluation_json_dir).mkdir(parents=True, exist_ok=True)
    Path("./backend/storage").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    if engine.dialect.name == "mysql":
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE candidate_responses MODIFY COLUMN media_blob LONGBLOB NULL")
                )
                mysql_tuning_statements = [
                    "CREATE INDEX idx_candidate_sessions_created_at ON candidate_sessions (created_at)",
                    (
                        "CREATE INDEX idx_candidate_responses_session_created "
                        "ON candidate_responses (session_id, created_at)"
                    ),
                    (
                        "CREATE INDEX idx_candidate_responses_session_question "
                        "ON candidate_responses (session_id, question_id)"
                    ),
                ]

                for statement in mysql_tuning_statements:
                    try:
                        conn.execute(text(statement))
                    except Exception:
                        # Index may already exist depending on prior runs/migrations.
                        continue
        except Exception:
            # Keep startup resilient if table/column is already in expected state.
            pass


@app.get("/")
def serve_home() -> FileResponse:
    return FileResponse(static_dir / "auth.html", headers=NO_CACHE_HEADERS)


@app.get("/auth")
def serve_auth() -> FileResponse:
    return FileResponse(static_dir / "auth.html", headers=NO_CACHE_HEADERS)


@app.get("/callback")
def serve_legacy_callback(request: Request) -> RedirectResponse:
    query = request.url.query
    target = "/api/auth/callback"
    if query:
        target = f"{target}?{query}"
    return RedirectResponse(url=target, status_code=307)


@app.get("/auth/callback")
def serve_auth_callback_alias(request: Request) -> RedirectResponse:
    query = request.url.query
    target = "/api/auth/callback"
    if query:
        target = f"{target}?{query}"
    return RedirectResponse(url=target, status_code=307)


@app.get("/interview")
def serve_interview() -> FileResponse:
    return FileResponse(static_dir / "index.html", headers=NO_CACHE_HEADERS)


@app.get("/admin")
def serve_admin_portal() -> FileResponse:
    return FileResponse(static_dir / "admin.html", headers=NO_CACHE_HEADERS)


@app.get("/admin/sessions/{session_id}")
def serve_admin_session_response(session_id: str) -> FileResponse:
    _ = session_id
    return FileResponse(static_dir / "admin_response.html", headers=NO_CACHE_HEADERS)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
