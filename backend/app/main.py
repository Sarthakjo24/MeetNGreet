from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, select, text

from .config import settings
from .database import Base, SessionLocal, engine
from .models import CandidateResponse, CandidateSession, Score, SessionQuestion, User
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

APP_BUILD_FINGERPRINT = "tw5-8000"
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-MeetnGreet-Build": APP_BUILD_FINGERPRINT,
}


def _ensure_users_name_column() -> None:
    try:
        inspector = inspect(engine)
        column_names = {column["name"] for column in inspector.get_columns("users")}
    except Exception:
        return

    add_statements: list[str] = []
    if "name" not in column_names:
        if engine.dialect.name == "sqlite":
            add_statements.append("ALTER TABLE users ADD COLUMN name VARCHAR(255)")
        else:
            add_statements.append("ALTER TABLE users ADD COLUMN name VARCHAR(255) NULL")
    if "candidate_id" not in column_names:
        if engine.dialect.name == "sqlite":
            add_statements.append("ALTER TABLE users ADD COLUMN candidate_id VARCHAR(320)")
        else:
            add_statements.append("ALTER TABLE users ADD COLUMN candidate_id VARCHAR(320) NULL")

    try:
        with engine.begin() as conn:
            for statement in add_statements:
                conn.execute(text(statement))
            try:
                conn.execute(text("CREATE UNIQUE INDEX uq_users_candidate_id ON users (candidate_id)"))
            except Exception:
                try:
                    conn.execute(text("CREATE INDEX ix_users_candidate_id ON users (candidate_id)"))
                except Exception:
                    # Keep startup resilient if index exists.
                    pass
    except Exception:
        # Keep startup resilient if the column already exists.
        pass


def _backfill_user_names() -> None:
    db = SessionLocal()
    try:
        users = db.scalars(select(User)).all()
        if not users:
            return

        changed = False
        for user in users:
            normalized_name = " ".join(str(user.name or "").strip().split())
            if normalized_name and "@" not in normalized_name:
                updated_name = normalized_name
            else:
                updated_name = _derive_name_from_email(user.email)

            updated_candidate_id = (user.email or "").strip().lower() or None

            if user.name != updated_name:
                user.name = updated_name
                changed = True
            if user.candidate_id != updated_candidate_id:
                user.candidate_id = updated_candidate_id
                changed = True

        if changed:
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _remove_candidate_response_detailed_feedback_column() -> None:
    try:
        inspector = inspect(engine)
        column_names = {column["name"] for column in inspector.get_columns("candidate_responses")}
    except Exception:
        return

    if "detailed_feedback" not in column_names:
        return

    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE candidate_responses DROP COLUMN detailed_feedback"))
    except Exception:
        # Keep startup resilient across database engines.
        pass


def _ensure_candidate_sessions_columns() -> None:
    try:
        inspector = inspect(engine)
        column_names = {column["name"] for column in inspector.get_columns("candidate_sessions")}
    except Exception:
        return

    add_statements: list[str] = []
    if "candidate_name" not in column_names:
        add_statements.append("ALTER TABLE candidate_sessions ADD COLUMN candidate_name VARCHAR(255) NULL")
    if "candidate_email" not in column_names:
        add_statements.append("ALTER TABLE candidate_sessions ADD COLUMN candidate_email VARCHAR(320) NULL")

    if not add_statements:
        return

    try:
        with engine.begin() as conn:
            for statement in add_statements:
                conn.execute(text(statement))
    except Exception:
        # Keep startup resilient across database engines.
        pass


def _ensure_session_questions_columns() -> None:
    try:
        inspector = inspect(engine)
        column_names = {column["name"] for column in inspector.get_columns("session_questions")}
    except Exception:
        return

    add_statements: list[str] = []
    if "candidate_name" not in column_names:
        add_statements.append("ALTER TABLE session_questions ADD COLUMN candidate_name VARCHAR(255) NULL")
    if "candidate_email" not in column_names:
        add_statements.append("ALTER TABLE session_questions ADD COLUMN candidate_email VARCHAR(320) NULL")

    if not add_statements:
        return

    try:
        with engine.begin() as conn:
            for statement in add_statements:
                conn.execute(text(statement))
    except Exception:
        # Keep startup resilient across database engines.
        pass


def _derive_name_from_email(email: str | None) -> str:
    local_part = str(email or "").strip().split("@", 1)[0]
    if not local_part:
        return "Candidate"
    parts = [part for part in local_part.replace("-", ".").replace("_", ".").split(".") if part]
    if not parts:
        return "Candidate"
    return " ".join(part.title() for part in parts)


def _migrate_candidate_responses_schema() -> None:
    try:
        inspector = inspect(engine)
        column_names = {column["name"] for column in inspector.get_columns("candidate_responses")}
    except Exception:
        return

    has_attempt_no = "attempt_no" in column_names
    has_candidate_name = "candidate_name" in column_names
    has_candidate_email = "candidate_email" in column_names
    has_legacy_score_columns = any(
        name in column_names
        for name in ("communication_score", "content_score", "confidence_score", "final_score")
    )

    # Fast path: schema already in target shape.
    if not has_attempt_no and has_candidate_name and has_candidate_email and not has_legacy_score_columns:
        return

    if engine.dialect.name == "sqlite" and (has_attempt_no or has_legacy_score_columns):
        try:
            with engine.begin() as conn:
                conn.execute(text("PRAGMA foreign_keys=OFF"))
                conn.execute(text("DROP TABLE IF EXISTS candidate_responses_new"))
                conn.execute(
                    text(
                        """
                        CREATE TABLE candidate_responses_new (
                            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                            session_id VARCHAR(36) NOT NULL,
                            question_id VARCHAR(32) NOT NULL,
                            candidate_name VARCHAR(255),
                            candidate_email VARCHAR(320),
                            media_filename VARCHAR(255) NOT NULL,
                            media_mime VARCHAR(120) NOT NULL,
                            media_blob BLOB,
                            media_path VARCHAR(500) NOT NULL,
                            duration_seconds FLOAT,
                            transcript TEXT,
                            created_at DATETIME NOT NULL,
                            CONSTRAINT uq_response_question UNIQUE (session_id, question_id),
                            FOREIGN KEY(session_id) REFERENCES candidate_sessions (id)
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        WITH ranked AS (
                            SELECT
                                cr.*,
                                ROW_NUMBER() OVER (
                                    PARTITION BY cr.session_id, cr.question_id
                                    ORDER BY cr.created_at DESC, cr.id DESC
                                ) AS rn
                            FROM candidate_responses cr
                        )
                        INSERT INTO candidate_responses_new (
                            id,
                            session_id,
                            question_id,
                            candidate_name,
                            candidate_email,
                            media_filename,
                            media_mime,
                            media_blob,
                            media_path,
                            duration_seconds,
                            transcript,
                            created_at
                        )
                        SELECT
                            r.id,
                            r.session_id,
                            r.question_id,
                            NULL,
                            COALESCE(
                                NULLIF(TRIM(u.email), ''),
                                NULLIF(TRIM(cs.candidate_id), '')
                            ) AS candidate_email,
                            r.media_filename,
                            r.media_mime,
                            r.media_blob,
                            r.media_path,
                            r.duration_seconds,
                            r.transcript,
                            r.created_at
                        FROM ranked r
                        LEFT JOIN candidate_sessions cs
                            ON cs.id = r.session_id
                        LEFT JOIN users u
                            ON LOWER(u.email) = LOWER(cs.candidate_id)
                        WHERE r.rn = 1
                        """
                    )
                )
                conn.execute(text("DROP TABLE candidate_responses"))
                conn.execute(text("ALTER TABLE candidate_responses_new RENAME TO candidate_responses"))
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_candidate_responses_session_id "
                        "ON candidate_responses (session_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_candidate_responses_question_id "
                        "ON candidate_responses (question_id)"
                    )
                )
                conn.execute(text("PRAGMA foreign_keys=ON"))
            return
        except Exception:
            # Fall through to generic migration path.
            pass

    try:
        with engine.begin() as conn:
            if not has_candidate_name:
                conn.execute(text("ALTER TABLE candidate_responses ADD COLUMN candidate_name VARCHAR(255) NULL"))
            if not has_candidate_email:
                conn.execute(text("ALTER TABLE candidate_responses ADD COLUMN candidate_email VARCHAR(320) NULL"))

            if has_attempt_no:
                # Keep the newest record per (session_id, question_id) before dropping attempt_no.
                if engine.dialect.name == "mysql":
                    conn.execute(
                        text(
                            """
                            DELETE cr1 FROM candidate_responses cr1
                            JOIN candidate_responses cr2
                              ON cr1.session_id = cr2.session_id
                             AND cr1.question_id = cr2.question_id
                             AND (
                                cr1.created_at < cr2.created_at
                                OR (cr1.created_at = cr2.created_at AND cr1.id < cr2.id)
                             )
                            """
                        )
                    )
                else:
                    conn.execute(
                        text(
                            """
                            DELETE FROM candidate_responses
                            WHERE id IN (
                                SELECT id FROM (
                                    SELECT
                                        id,
                                        ROW_NUMBER() OVER (
                                            PARTITION BY session_id, question_id
                                            ORDER BY created_at DESC, id DESC
                                        ) AS rn
                                    FROM candidate_responses
                                ) ranked
                                WHERE ranked.rn > 1
                            )
                            """
                        )
                    )

                try:
                    conn.execute(text("ALTER TABLE candidate_responses DROP INDEX uq_response_attempt"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE candidate_responses DROP CONSTRAINT uq_response_attempt"))
                except Exception:
                    pass

                conn.execute(text("ALTER TABLE candidate_responses DROP COLUMN attempt_no"))
                try:
                    conn.execute(
                        text(
                            "ALTER TABLE candidate_responses "
                            "ADD CONSTRAINT uq_response_question UNIQUE (session_id, question_id)"
                        )
                    )
                except Exception:
                    try:
                        conn.execute(
                            text(
                                "CREATE UNIQUE INDEX uq_response_question "
                                "ON candidate_responses (session_id, question_id)"
                            )
                        )
                    except Exception:
                        pass

            for legacy_score_col in (
                "communication_score",
                "content_score",
                "confidence_score",
                "final_score",
            ):
                if legacy_score_col in column_names:
                    try:
                        conn.execute(
                            text(
                                f"ALTER TABLE candidate_responses DROP COLUMN {legacy_score_col}"
                            )
                        )
                    except Exception:
                        pass
    except Exception:
        # Keep startup resilient if migration is not supported by the active engine.
        pass


def _backfill_candidate_response_identity_fields() -> None:
    db = SessionLocal()
    try:
        responses = db.scalars(select(CandidateResponse)).all()
        if not responses:
            return

        sessions = db.scalars(select(CandidateSession)).all()
        session_map = {session.id: session for session in sessions}

        users = db.scalars(select(User)).all()
        user_by_email = {
            (user.email or "").strip().lower(): user
            for user in users
            if user.email
        }

        changed = False
        for response in responses:
            session = session_map.get(response.session_id)
            base_email = (session.candidate_id if session else "").strip().lower()
            session_email = (session.candidate_email if session else "").strip().lower()
            user = user_by_email.get((session_email or base_email)) if (session_email or base_email) else None

            candidate_email = (response.candidate_email or "").strip().lower()
            if not candidate_email:
                candidate_email = (session_email or (user.email if user else base_email) or "").strip().lower()

            candidate_name = " ".join(str(response.candidate_name or "").strip().split())
            if not candidate_name or "@" in candidate_name:
                session_name = " ".join(str(session.candidate_name or "").strip().split()) if session else ""
                user_name = " ".join(str(user.name or "").strip().split()) if user else ""
                candidate_name = user_name if user_name else _derive_name_from_email(candidate_email)
                if session_name:
                    candidate_name = session_name

            if response.candidate_email != candidate_email or response.candidate_name != candidate_name:
                response.candidate_email = candidate_email
                response.candidate_name = candidate_name
                changed = True

        if changed:
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _backfill_session_and_question_identity() -> None:
    db = SessionLocal()
    try:
        sessions = db.scalars(select(CandidateSession)).all()
        if not sessions:
            return

        users = db.scalars(select(User)).all()
        user_by_email = {
            (user.email or "").strip().lower(): user
            for user in users
            if user.email
        }

        questions = db.scalars(select(SessionQuestion)).all()
        questions_by_session: dict[str, list[SessionQuestion]] = {}
        for question in questions:
            questions_by_session.setdefault(question.session_id, []).append(question)

        changed = False
        for session in sessions:
            base_email = (session.candidate_id or "").strip().lower()
            session_email = (session.candidate_email or "").strip().lower()
            user = user_by_email.get((session_email or base_email)) if (session_email or base_email) else None

            candidate_email = (session_email or (user.email if user else base_email) or "").strip().lower()
            user_name = " ".join(str(user.name or "").strip().split()) if user else ""
            session_name = " ".join(str(session.candidate_name or "").strip().split())
            candidate_name = session_name if session_name and "@" not in session_name else (user_name or _derive_name_from_email(candidate_email))

            if (
                session.candidate_email != candidate_email
                or session.candidate_name != candidate_name
            ):
                session.candidate_email = candidate_email
                session.candidate_name = candidate_name
                changed = True

            for question in questions_by_session.get(session.id, []):
                if question.candidate_email != candidate_email or question.candidate_name != candidate_name:
                    question.candidate_email = candidate_email
                    question.candidate_name = candidate_name
                    changed = True

        if changed:
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _ensure_scores_table() -> None:
    try:
        Score.__table__.create(bind=engine, checkfirst=True)
    except Exception:
        pass


def _backfill_scores_from_legacy_columns() -> None:
    try:
        inspector = inspect(engine)
        session_columns = {column["name"] for column in inspector.get_columns("candidate_sessions")}
        response_columns = {column["name"] for column in inspector.get_columns("candidate_responses")}
    except Exception:
        return

    has_session_scores = any(
        name in session_columns
        for name in ("overall_score", "communication_total", "content_total", "confidence_total")
    )
    has_response_scores = any(
        name in response_columns
        for name in ("communication_score", "content_score", "confidence_score", "final_score")
    )
    if not has_session_scores and not has_response_scores:
        return

    db = SessionLocal()
    try:
        sessions = db.scalars(select(CandidateSession)).all()
        if not sessions:
            return

        for session in sessions:
            candidate_id = (session.candidate_id or "").strip().lower()
            if not candidate_id:
                continue

            user = db.scalar(select(User).where(User.candidate_id == candidate_id))
            if not user or not user.candidate_id:
                continue

            ai_total: float | None = None
            ai_communication: float | None = None
            ai_content: float | None = None
            ai_confidence: float | None = None

            if has_session_scores:
                session_score_select = ", ".join(
                    [
                        "overall_score" if "overall_score" in session_columns else "NULL AS overall_score",
                        (
                            "communication_total"
                            if "communication_total" in session_columns
                            else "NULL AS communication_total"
                        ),
                        "content_total" if "content_total" in session_columns else "NULL AS content_total",
                        (
                            "confidence_total"
                            if "confidence_total" in session_columns
                            else "NULL AS confidence_total"
                        ),
                    ]
                )
                session_legacy = db.execute(
                    text(
                        f"""
                        SELECT {session_score_select}
                        FROM candidate_sessions
                        WHERE id = :session_id
                        """
                    ),
                    {"session_id": session.id},
                ).mappings().first()
                if session_legacy:
                    question_count = (
                        db.scalar(
                            select(func.count())
                            .select_from(SessionQuestion)
                            .where(SessionQuestion.session_id == session.id)
                        )
                        or 0
                    )
                    ai_total = (
                        float(session_legacy["overall_score"])
                        if session_legacy["overall_score"] is not None
                        else None
                    )
                    if question_count > 0:
                        if session_legacy["communication_total"] is not None:
                            ai_communication = round(
                                float(session_legacy["communication_total"]) / float(question_count),
                                2,
                            )
                        if session_legacy["content_total"] is not None:
                            ai_content = round(
                                float(session_legacy["content_total"]) / float(question_count),
                                2,
                            )
                        if session_legacy["confidence_total"] is not None:
                            ai_confidence = round(
                                float(session_legacy["confidence_total"]) / float(question_count),
                                2,
                            )

            if has_response_scores and (
                ai_total is None
                or ai_communication is None
                or ai_content is None
                or ai_confidence is None
            ):
                response_score_select = ", ".join(
                    [
                        (
                            "AVG(communication_score) AS avg_communication"
                            if "communication_score" in response_columns
                            else "NULL AS avg_communication"
                        ),
                        (
                            "AVG(content_score) AS avg_content"
                            if "content_score" in response_columns
                            else "NULL AS avg_content"
                        ),
                        (
                            "AVG(confidence_score) AS avg_confidence"
                            if "confidence_score" in response_columns
                            else "NULL AS avg_confidence"
                        ),
                        (
                            "AVG(final_score) AS avg_final"
                            if "final_score" in response_columns
                            else "NULL AS avg_final"
                        ),
                    ]
                )
                response_legacy = db.execute(
                    text(
                        f"""
                        SELECT
                            {response_score_select}
                        FROM candidate_responses
                        WHERE session_id = :session_id
                        """
                    ),
                    {"session_id": session.id},
                ).mappings().first()
                if response_legacy:
                    if ai_communication is None and response_legacy["avg_communication"] is not None:
                        ai_communication = round(float(response_legacy["avg_communication"]), 2)
                    if ai_content is None and response_legacy["avg_content"] is not None:
                        ai_content = round(float(response_legacy["avg_content"]), 2)
                    if ai_confidence is None and response_legacy["avg_confidence"] is not None:
                        ai_confidence = round(float(response_legacy["avg_confidence"]), 2)
                    if ai_total is None and response_legacy["avg_final"] is not None:
                        ai_total = round(float(response_legacy["avg_final"]), 2)

            score_row = db.scalar(select(Score).where(Score.session_id == session.id))
            if not score_row:
                score_row = Score(session_id=session.id, candidate_id=user.candidate_id)
                db.add(score_row)

            score_row.candidate_id = user.candidate_id
            score_row.candidate_name = session.candidate_name
            score_row.candidate_email = session.candidate_email
            if ai_communication is not None:
                score_row.ai_communication_score = ai_communication
            if ai_content is not None:
                score_row.ai_content_score = ai_content
            if ai_confidence is not None:
                score_row.ai_confidence_score = ai_confidence
            if ai_total is not None:
                score_row.ai_total_score = ai_total

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _drop_legacy_score_columns() -> None:
    try:
        inspector = inspect(engine)
        session_columns = {column["name"] for column in inspector.get_columns("candidate_sessions")}
        response_columns = {column["name"] for column in inspector.get_columns("candidate_responses")}
    except Exception:
        return

    session_score_columns = [
        "overall_score",
        "communication_total",
        "content_total",
        "confidence_total",
    ]
    response_score_columns = [
        "communication_score",
        "content_score",
        "confidence_score",
        "final_score",
    ]

    if engine.dialect.name == "sqlite":
        if any(name in session_columns for name in session_score_columns):
            try:
                with engine.begin() as conn:
                    conn.execute(text("PRAGMA foreign_keys=OFF"))
                    conn.execute(text("DROP TABLE IF EXISTS candidate_sessions_new"))
                    conn.execute(
                        text(
                            """
                            CREATE TABLE candidate_sessions_new (
                                id VARCHAR(36) NOT NULL PRIMARY KEY,
                                candidate_id VARCHAR(320) NOT NULL,
                                candidate_name VARCHAR(255),
                                candidate_email VARCHAR(320),
                                status VARCHAR(24) NOT NULL,
                                status_label VARCHAR(24),
                                created_at DATETIME NOT NULL,
                                evaluated_at DATETIME
                            )
                            """
                        )
                    )
                    conn.execute(
                        text(
                            """
                            INSERT INTO candidate_sessions_new (
                                id,
                                candidate_id,
                                candidate_name,
                                candidate_email,
                                status,
                                status_label,
                                created_at,
                                evaluated_at
                            )
                            SELECT
                                id,
                                candidate_id,
                                candidate_name,
                                candidate_email,
                                status,
                                status_label,
                                created_at,
                                evaluated_at
                            FROM candidate_sessions
                            """
                        )
                    )
                    conn.execute(text("DROP TABLE candidate_sessions"))
                    conn.execute(text("ALTER TABLE candidate_sessions_new RENAME TO candidate_sessions"))
                    conn.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_candidate_sessions_id "
                            "ON candidate_sessions (id)"
                        )
                    )
                    conn.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_candidate_sessions_candidate_id "
                            "ON candidate_sessions (candidate_id)"
                        )
                    )
                    conn.execute(text("PRAGMA foreign_keys=ON"))
            except Exception:
                pass

        # candidate_responses score columns are removed in _migrate_candidate_responses_schema.
        return

    with engine.begin() as conn:
        for column_name in session_score_columns:
            if column_name in session_columns:
                try:
                    conn.execute(
                        text(f"ALTER TABLE candidate_sessions DROP COLUMN {column_name}")
                    )
                except Exception:
                    continue
        for column_name in response_score_columns:
            if column_name in response_columns:
                try:
                    conn.execute(
                        text(f"ALTER TABLE candidate_responses DROP COLUMN {column_name}")
                    )
                except Exception:
                    continue


@app.on_event("startup")
def on_startup() -> None:
    Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
    Path("./backend/storage").mkdir(parents=True, exist_ok=True)
    _ensure_users_name_column()
    Base.metadata.create_all(bind=engine)
    _ensure_scores_table()
    _ensure_users_name_column()
    _backfill_user_names()
    _ensure_candidate_sessions_columns()
    _ensure_session_questions_columns()
    _remove_candidate_response_detailed_feedback_column()
    _backfill_scores_from_legacy_columns()
    _migrate_candidate_responses_schema()
    _drop_legacy_score_columns()
    _backfill_session_and_question_identity()
    _backfill_candidate_response_identity_fields()

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


@app.get("/admin/sessions/{session_id}/videos")
def serve_admin_session_videos(session_id: str) -> FileResponse:
    _ = session_id
    return FileResponse(static_dir / "admin_videos.html", headers=NO_CACHE_HEADERS)


@app.get("/admin/sessions/{session_id}")
def serve_admin_session_response(session_id: str) -> FileResponse:
    _ = session_id
    return FileResponse(static_dir / "admin_response.html", headers=NO_CACHE_HEADERS)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
