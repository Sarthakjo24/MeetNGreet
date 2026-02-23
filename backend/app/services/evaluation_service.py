import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import CandidateResponse, CandidateSession, SessionQuestion
from .llm_service import LLMScoringService
from .scoring_service import ScoringService
from .transcription_service import TranscriptionService
from .video_service import VideoAnalysisService


class EvaluationService:
    def __init__(self) -> None:
        self.transcription_service = TranscriptionService()
        self.video_service = VideoAnalysisService()
        self.scoring_service = ScoringService()
        self.llm_service = LLMScoringService()
        self.evaluation_json_dir = Path(settings.evaluation_json_dir)
        self.evaluation_json_dir.mkdir(parents=True, exist_ok=True)

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
        question_scores: list[float] = []

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

            feedback_payload = {
                "feedback": score["feedback"],
                "strengths": score.get("strengths", []),
                "weaknesses": score.get("weaknesses", []),
            }

            response.communication_score = score["communication_score"]
            response.content_score = score["content_score"]
            response.confidence_score = score["confidence_score"]
            response.final_score = score["final_score"]
            response.detailed_feedback = json.dumps(feedback_payload, ensure_ascii=False)

            question_scores.append(score["final_score"])
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

        final_score = round(sum(question_scores) / len(question_scores), 2)
        status_label = self.scoring_service.classify_score(final_score)

        session.overall_score = final_score
        session.status_label = status_label
        session.status = "completed"
        session.evaluated_at = datetime.utcnow()

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

        self._persist_evaluation_json(session_id=session.id, payload=result)
        return result

    def _persist_evaluation_json(self, session_id: str, payload: dict) -> None:
        file_path = self.evaluation_json_dir / f"{session_id}.json"
        with file_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
