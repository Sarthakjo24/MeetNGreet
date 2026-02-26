import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CandidateResponse, CandidateSession, Score, SessionQuestion, User
from .llm_service import LLMScoringService
from .mysql_sync_service import get_mysql_sync_service
from .scoring_service import ScoringService
from .transcription_service import TranscriptionService
from .video_service import VideoAnalysisService

logger = logging.getLogger(__name__)


class EvaluationService:
    def __init__(self) -> None:
        self.transcription_service = TranscriptionService()
        self.video_service = VideoAnalysisService()
        self.scoring_service = ScoringService()
        self.llm_service = LLMScoringService()
        self.mysql_sync_service = get_mysql_sync_service()

    def evaluate_session(self, db: Session, session_id: str) -> dict:
        session = db.scalar(select(CandidateSession).where(CandidateSession.id == session_id))
        if not session:
            raise ValueError("Session not found")

        questions = db.scalars(
            select(SessionQuestion)
            .where(SessionQuestion.session_id == session_id)
            .order_by(SessionQuestion.order_index.asc())
        ).all()

        responses = db.scalars(
            select(CandidateResponse).where(CandidateResponse.session_id == session_id)
        ).all()

        response_map = {r.question_id: r for r in responses}
        question_results: list[dict] = []
        communication_total = 0.0
        content_total = 0.0
        confidence_total = 0.0

        for question in questions:
            response = response_map.get(question.question_id)
            if not response:
                continue

            media_bytes = b""
            media_path = Path(response.media_path) if response.media_path else None
            if media_path and media_path.exists():
                media_bytes = media_path.read_bytes()
            elif response.media_blob:
                media_bytes = response.media_blob

            transcript = self.transcription_service.transcribe(
                media_bytes=media_bytes,
                file_name=response.media_filename,
                transcript_hint=response.transcript,
            )
            response.transcript = transcript

            video_metrics = self.video_service.analyze(response.media_path)
            llm_scores = self.llm_service.evaluate(
                question_text=question.question_text,
                transcript=transcript,
                video_metrics=video_metrics,
            )

            if not llm_scores:
                raise ValueError(
                    "OpenAI evaluation is required but unavailable. "
                    "Set USE_OPENAI_EVAL=true and provide OPENAI_API_KEY in .env."
                )

            score = self.scoring_service.score_answer(
                question_text=question.question_text,
                transcript=transcript,
                video_metrics=video_metrics,
                llm_override=llm_scores,
            )

            communication_total += score["communication_score"]
            content_total += score["content_score"]
            confidence_total += score["confidence_score"]
            question_results.append(
                {
                    "question_id": question.question_id,
                    "communication_score": score["communication_score"],
                    "content_score": score["content_score"],
                    "confidence_score": score["confidence_score"],
                    "final_score": score["final_score"],
                    "feedback": score["feedback"],
                    "strengths": score.get("strengths", []),
                    "weaknesses": score.get("weaknesses", []),
                }
            )

        if not question_results:
            raise ValueError("No responses available for evaluation")

        evaluated_count = len(question_results)
        weighted_total = (
            (communication_total * self.scoring_service.weights["communication"])
            + (content_total * self.scoring_service.weights["content"])
            + (confidence_total * self.scoring_service.weights["confidence"])
        )
        final_score = round(weighted_total / evaluated_count, 2)
        status_label = self.scoring_service.classify_score(final_score)

        session.status_label = status_label
        session.status = "completed"
        session.evaluated_at = datetime.utcnow()

        ai_communication_score = round(communication_total / evaluated_count, 2)
        ai_content_score = round(content_total / evaluated_count, 2)
        ai_confidence_score = round(confidence_total / evaluated_count, 2)

        score_candidate_id = (session.candidate_id or "").strip().lower()
        score_user = (
            db.scalar(select(User).where(User.candidate_id == score_candidate_id))
            if score_candidate_id
            else None
        )
        if score_user and score_user.candidate_id:
            score_row = db.scalar(select(Score).where(Score.session_id == session.id))
            if not score_row:
                score_row = Score(
                    session_id=session.id,
                    candidate_id=score_user.candidate_id,
                )
                db.add(score_row)

            score_row.candidate_id = score_user.candidate_id
            score_row.candidate_name = session.candidate_name
            score_row.candidate_email = session.candidate_email
            score_row.ai_communication_score = ai_communication_score
            score_row.ai_content_score = ai_content_score
            score_row.ai_confidence_score = ai_confidence_score
            score_row.ai_total_score = final_score
        else:
            logger.warning(
                "Skipping score table upsert for session %s: missing user candidate_id mapping.",
                session.id,
            )

        db.commit()

        result = {
            "session_id": session.id,
            "candidate_id": session.candidate_id,
            "final_score": final_score,
            "status_label": status_label,
            "question_results": question_results,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "submitted_at": session.evaluated_at.isoformat() if session.evaluated_at else None,
        }

        try:
            self.mysql_sync_service.sync_session(source_db=db, session_id=session.id)
        except Exception:
            # Mirror sync failures must not break primary evaluation flow.
            logger.exception("MySQL mirror sync failed after evaluating session %s", session.id)

        return result
