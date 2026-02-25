import logging
from urllib.parse import quote_plus

from sqlalchemy import delete, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings
from ..database import Base, engine as primary_engine
from ..models import CandidateResponse, CandidateSession, SessionQuestion, User

logger = logging.getLogger(__name__)


def _build_mysql_target_url() -> str | None:
    if primary_engine.dialect.name == "mysql":
        return None

    if settings.database_url and settings.database_url.startswith("mysql"):
        return settings.database_url

    mysql_user = (settings.mysql_user or "").strip()
    mysql_host = (settings.mysql_host or "").strip()
    mysql_database = (settings.mysql_database or "").strip()
    if not mysql_user or not mysql_host or not mysql_database:
        return None

    mysql_port = settings.mysql_port
    mysql_password = quote_plus(settings.mysql_password or "")
    return (
        "mysql+pymysql://"
        f"{mysql_user}:{mysql_password}"
        f"@{mysql_host}:{mysql_port}/{mysql_database}"
    )


class MysqlSyncService:
    def __init__(self) -> None:
        self.enabled = False
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

        mysql_url = _build_mysql_target_url()
        if not mysql_url:
            return

        try:
            from sqlalchemy import create_engine

            self._engine = create_engine(
                mysql_url,
                future=True,
                pool_pre_ping=True,
                connect_args={
                    "connect_timeout": 5,
                    "read_timeout": 10,
                    "write_timeout": 10,
                },
            )
            self._session_factory = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False,
                future=True,
            )
            self.enabled = True
        except Exception:
            logger.exception("MySQL sync disabled: failed to initialize MySQL engine.")

    def _ensure_target_schema(self) -> None:
        if not self.enabled or not self._engine:
            return

        Base.metadata.create_all(bind=self._engine)
        inspector = inspect(self._engine)

        users_cols = {column["name"] for column in inspector.get_columns("users")}
        session_cols = {column["name"] for column in inspector.get_columns("candidate_sessions")}
        question_cols = {column["name"] for column in inspector.get_columns("session_questions")}
        response_cols = {column["name"] for column in inspector.get_columns("candidate_responses")}

        with self._engine.begin() as conn:
            if "name" not in users_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR(255) NULL"))

            if "candidate_name" not in session_cols:
                conn.execute(text("ALTER TABLE candidate_sessions ADD COLUMN candidate_name VARCHAR(255) NULL"))
            if "candidate_email" not in session_cols:
                conn.execute(text("ALTER TABLE candidate_sessions ADD COLUMN candidate_email VARCHAR(320) NULL"))
            if "communication_total" not in session_cols:
                conn.execute(text("ALTER TABLE candidate_sessions ADD COLUMN communication_total FLOAT NULL"))
            if "content_total" not in session_cols:
                conn.execute(text("ALTER TABLE candidate_sessions ADD COLUMN content_total FLOAT NULL"))
            if "confidence_total" not in session_cols:
                conn.execute(text("ALTER TABLE candidate_sessions ADD COLUMN confidence_total FLOAT NULL"))

            if "candidate_name" not in question_cols:
                conn.execute(text("ALTER TABLE session_questions ADD COLUMN candidate_name VARCHAR(255) NULL"))
            if "candidate_email" not in question_cols:
                conn.execute(text("ALTER TABLE session_questions ADD COLUMN candidate_email VARCHAR(320) NULL"))

            if "candidate_name" not in response_cols:
                conn.execute(text("ALTER TABLE candidate_responses ADD COLUMN candidate_name VARCHAR(255) NULL"))
            if "candidate_email" not in response_cols:
                conn.execute(text("ALTER TABLE candidate_responses ADD COLUMN candidate_email VARCHAR(320) NULL"))
            if "attempt_no" in response_cols:
                conn.execute(
                    text(
                        "ALTER TABLE candidate_responses "
                        "MODIFY COLUMN attempt_no INT NOT NULL DEFAULT 1"
                    )
                )

    def sync_session(self, source_db: Session, session_id: str) -> None:
        if not self.enabled or not self._session_factory:
            return

        try:
            self._ensure_target_schema()

            session_row = source_db.scalar(
                select(CandidateSession).where(CandidateSession.id == session_id)
            )
            if not session_row:
                return

            question_rows = source_db.scalars(
                select(SessionQuestion).where(SessionQuestion.session_id == session_id)
            ).all()
            response_rows = source_db.scalars(
                select(CandidateResponse).where(CandidateResponse.session_id == session_id)
            ).all()

            lookup_email = (
                (session_row.candidate_email or session_row.candidate_id or "").strip().lower()
            )
            user_row = (
                source_db.scalar(select(User).where(User.email == lookup_email))
                if lookup_email
                else None
            )

            target_db = self._session_factory()
            try:
                if user_row:
                    target_user = target_db.scalar(select(User).where(User.email == user_row.email))
                    if not target_user:
                        target_user = User(
                            unique_id=user_row.unique_id,
                            name=user_row.name,
                            email=user_row.email,
                            provider=user_row.provider,
                            created_at=user_row.created_at,
                        )
                        target_db.add(target_user)
                    else:
                        target_user.unique_id = user_row.unique_id
                        target_user.name = user_row.name
                        target_user.provider = user_row.provider
                        target_user.created_at = user_row.created_at

                target_session = target_db.scalar(
                    select(CandidateSession).where(CandidateSession.id == session_id)
                )
                if not target_session:
                    target_session = CandidateSession(
                        id=session_row.id,
                        candidate_id=session_row.candidate_id,
                        candidate_name=session_row.candidate_name,
                        candidate_email=session_row.candidate_email,
                        status=session_row.status,
                        overall_score=session_row.overall_score,
                        communication_total=session_row.communication_total,
                        content_total=session_row.content_total,
                        confidence_total=session_row.confidence_total,
                        status_label=session_row.status_label,
                        created_at=session_row.created_at,
                        evaluated_at=session_row.evaluated_at,
                    )
                    target_db.add(target_session)
                else:
                    target_session.candidate_id = session_row.candidate_id
                    target_session.candidate_name = session_row.candidate_name
                    target_session.candidate_email = session_row.candidate_email
                    target_session.status = session_row.status
                    target_session.overall_score = session_row.overall_score
                    target_session.communication_total = session_row.communication_total
                    target_session.content_total = session_row.content_total
                    target_session.confidence_total = session_row.confidence_total
                    target_session.status_label = session_row.status_label
                    target_session.created_at = session_row.created_at
                    target_session.evaluated_at = session_row.evaluated_at

                existing_questions = target_db.scalars(
                    select(SessionQuestion).where(SessionQuestion.session_id == session_id)
                ).all()
                question_by_id = {question.question_id: question for question in existing_questions}
                source_question_ids = {question.question_id for question in question_rows}

                for question in question_rows:
                    target_question = question_by_id.get(question.question_id)
                    if not target_question:
                        target_question = SessionQuestion(
                            session_id=question.session_id,
                            question_id=question.question_id,
                            candidate_name=question.candidate_name,
                            candidate_email=question.candidate_email,
                            question_text=question.question_text,
                            topic=question.topic,
                            question_type=question.question_type,
                            order_index=question.order_index,
                        )
                        target_db.add(target_question)
                    else:
                        target_question.candidate_name = question.candidate_name
                        target_question.candidate_email = question.candidate_email
                        target_question.question_text = question.question_text
                        target_question.topic = question.topic
                        target_question.question_type = question.question_type
                        target_question.order_index = question.order_index

                for question in existing_questions:
                    if question.question_id not in source_question_ids:
                        target_db.delete(question)

                existing_responses = target_db.scalars(
                    select(CandidateResponse).where(CandidateResponse.session_id == session_id)
                ).all()

                response_by_question: dict[str, CandidateResponse] = {}
                for existing in sorted(
                    existing_responses,
                    key=lambda item: (item.created_at, item.id),
                    reverse=True,
                ):
                    if existing.question_id in response_by_question:
                        target_db.delete(existing)
                        continue
                    response_by_question[existing.question_id] = existing

                source_response_ids = {response.question_id for response in response_rows}
                for response in response_rows:
                    target_response = response_by_question.get(response.question_id)
                    if not target_response:
                        target_response = CandidateResponse(
                            session_id=response.session_id,
                            question_id=response.question_id,
                            candidate_name=response.candidate_name,
                            candidate_email=response.candidate_email,
                            media_filename=response.media_filename,
                            media_mime=response.media_mime,
                            media_blob=response.media_blob,
                            media_path=response.media_path,
                            duration_seconds=response.duration_seconds,
                            transcript=response.transcript,
                            communication_score=response.communication_score,
                            content_score=response.content_score,
                            confidence_score=response.confidence_score,
                            final_score=response.final_score,
                            created_at=response.created_at,
                        )
                        target_db.add(target_response)
                    else:
                        target_response.candidate_name = response.candidate_name
                        target_response.candidate_email = response.candidate_email
                        target_response.media_filename = response.media_filename
                        target_response.media_mime = response.media_mime
                        target_response.media_blob = response.media_blob
                        target_response.media_path = response.media_path
                        target_response.duration_seconds = response.duration_seconds
                        target_response.transcript = response.transcript
                        target_response.communication_score = response.communication_score
                        target_response.content_score = response.content_score
                        target_response.confidence_score = response.confidence_score
                        target_response.final_score = response.final_score
                        target_response.created_at = response.created_at

                for existing in existing_responses:
                    if existing.question_id not in source_response_ids:
                        target_db.delete(existing)

                target_db.commit()
            except Exception:
                target_db.rollback()
                logger.exception("MySQL sync failed for session %s", session_id)
            finally:
                target_db.close()
        except Exception as exc:
            logger.warning(
                "MySQL sync failed before transaction for session %s: %s",
                session_id,
                exc,
            )
            self.enabled = False
            logger.warning("MySQL sync has been disabled for this process after connection failure.")

    def delete_session(self, session_id: str) -> None:
        if not self.enabled or not self._session_factory:
            return

        try:
            target_db = self._session_factory()
            try:
                target_db.execute(
                    delete(CandidateResponse).where(CandidateResponse.session_id == session_id)
                )
                target_db.execute(
                    delete(SessionQuestion).where(SessionQuestion.session_id == session_id)
                )
                target_db.execute(
                    delete(CandidateSession).where(CandidateSession.id == session_id)
                )
                target_db.commit()
            except Exception:
                target_db.rollback()
                logger.exception("MySQL delete sync failed for session %s", session_id)
            finally:
                target_db.close()
        except Exception as exc:
            logger.warning(
                "MySQL delete sync failed before transaction for session %s: %s",
                session_id,
                exc,
            )
            self.enabled = False
            logger.warning("MySQL sync has been disabled for this process after connection failure.")


_mysql_sync_service_singleton: MysqlSyncService | None = None


def get_mysql_sync_service() -> MysqlSyncService:
    global _mysql_sync_service_singleton
    if _mysql_sync_service_singleton is None:
        _mysql_sync_service_singleton = MysqlSyncService()
    return _mysql_sync_service_singleton
