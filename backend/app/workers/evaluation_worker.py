import logging

from sqlalchemy import select

from ..database import SessionLocal
from ..logging_context import bind_log_context
from ..models import CandidateSession
from ..services.evaluation_service import EvaluationService
from ..services.transcription_service import TranscriptionService

logger = logging.getLogger(__name__)
_shared_transcription_service: TranscriptionService | None = None


def evaluate_session_job(session_id: str) -> None:
    global _shared_transcription_service
    if _shared_transcription_service is None:
        _shared_transcription_service = TranscriptionService()

    db = SessionLocal()
    try:
        job_id = f"eval:{session_id}"
        with bind_log_context(job_id=job_id, session_id=session_id):
            logger.info("Evaluation job started.")
            evaluation_service = EvaluationService()
            evaluation_service.transcription_service = _shared_transcription_service
            evaluation_service.evaluate_session(db=db, session_id=session_id)
            logger.info("Evaluation job completed.")
    except Exception:
        with bind_log_context(job_id=f"eval:{session_id}", session_id=session_id):
            logger.exception("Evaluation job failed.")
        try:
            session = db.scalar(select(CandidateSession).where(CandidateSession.id == session_id))
            if session and session.status != "completed":
                session.status = "submitted"
                db.commit()
        except Exception:
            logger.exception(
                "Failed to update status for session %s after evaluation failure",
                session_id,
            )
        raise
    finally:
        db.close()
