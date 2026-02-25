import logging
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import CandidateResponse, CandidateSession, SessionQuestion, User
from ..schemas import (
    AdminDeleteOut,
    AdminResultOut,
    AdminSessionDetailOut,
    CandidateSessionOut,
    EvaluationSummaryOut,
    SessionProgressOut,
    UploadStatusOut,
    UploadResponseOut,
)
from ..security import CurrentUser, get_current_user
from ..services.evaluation_service import EvaluationService
from ..services.mysql_sync_service import get_mysql_sync_service
from ..services.question_service import QuestionService
from ..services.storage_service import MediaStorageService
from ..services.transcription_service import TranscriptionService

router = APIRouter(prefix="/api", tags=["Interview"])

logger = logging.getLogger(__name__)
question_service = QuestionService()
storage_service = MediaStorageService()
mysql_sync_service = get_mysql_sync_service()
_evaluation_service: EvaluationService | None = None
_evaluation_lock = threading.Lock()
_evaluation_inflight: set[str] = set()


def _get_evaluation_service() -> EvaluationService:
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = EvaluationService()
    return _evaluation_service


def _evaluate_session_background(session_id: str) -> None:
    retry_delays = [0.0, 2.0, 5.0]
    for idx, delay_seconds in enumerate(retry_delays):
        if delay_seconds > 0:
            time.sleep(delay_seconds)

        db = SessionLocal()
        try:
            _get_evaluation_service().evaluate_session(db=db, session_id=session_id)
            return
        except Exception:
            logger.exception(
                "Background evaluation attempt %s failed for session %s",
                idx + 1,
                session_id,
            )
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
        finally:
            db.close()


def _enqueue_session_evaluation(session_id: str) -> None:
    with _evaluation_lock:
        if session_id in _evaluation_inflight:
            return
        _evaluation_inflight.add(session_id)

    def _runner() -> None:
        try:
            _evaluate_session_background(session_id=session_id)
        finally:
            with _evaluation_lock:
                _evaluation_inflight.discard(session_id)

    threading.Thread(
        target=_runner,
        name=f"session-eval-{session_id[:8]}",
        daemon=True,
    ).start()


def _ensure_session_access(session: CandidateSession, current_user: CurrentUser) -> None:
    if session.candidate_id != current_user.email:
        raise HTTPException(status_code=403, detail="Not authorized to access this session.")


def _derive_name_from_email(email: str | None) -> str:
    local_part = str(email or "").strip().split("@", 1)[0]
    parts = [item for item in re.split(r"[._+\-\s]+", local_part) if item]
    if not parts:
        return "Candidate"
    return " ".join(part.title() for part in parts)


def _resolve_candidate_name(name: str | None, email: str | None) -> str:
    normalized_name = " ".join(str(name or "").strip().split())
    if normalized_name and "@" not in normalized_name:
        return normalized_name
    return _derive_name_from_email(email)


def _resolve_session_candidate_identity(db: Session, session: CandidateSession) -> tuple[str, str]:
    session_name = " ".join(str(session.candidate_name or "").strip().split())
    session_email = (session.candidate_email or "").strip().lower()
    if session_name and session_email:
        return session_name, session_email

    lookup_key = (session.candidate_id or "").strip().lower()
    user = db.scalar(select(User).where(User.email == lookup_key)) if lookup_key else None
    candidate_email = (session_email or (user.email if user else lookup_key) or "").strip().lower()
    candidate_name = _resolve_candidate_name(
        session_name or (user.name if user else None),
        candidate_email,
    )
    return candidate_name, candidate_email


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _session_upload_counts(db: Session, session_id: str) -> tuple[int, int]:
    total_questions = db.scalar(
        select(func.count())
        .select_from(SessionQuestion)
        .where(SessionQuestion.session_id == session_id)
    ) or 0
    uploaded_count = db.scalar(
        select(func.count(func.distinct(CandidateResponse.question_id)))
        .select_from(CandidateResponse)
        .where(CandidateResponse.session_id == session_id)
    ) or 0
    return int(total_questions), int(uploaded_count)


def _schedule_session_evaluation_if_ready(
    db: Session,
    session: CandidateSession,
) -> bool:
    total_questions, uploaded_count = _session_upload_counts(db=db, session_id=session.id)
    if total_questions <= 0 or uploaded_count < total_questions:
        return False
    if session.status == "completed" and session.overall_score is not None:
        return True

    session.status = "submitted"
    db.commit()
    _enqueue_session_evaluation(session.id)
    return False


@router.post("/candidates/start", response_model=CandidateSessionOut)
def start_candidate_session(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        selected_questions = question_service.select_questions()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    session_id = str(uuid4())
    candidate_id = current_user.email.strip().lower()
    user = db.scalar(select(User).where(User.unique_id == current_user.unique_id))
    candidate_email = (user.email if user and user.email else candidate_id).strip().lower()
    candidate_name = _resolve_candidate_name(
        user.name if user else None,
        candidate_email,
    )

    session = CandidateSession(
        id=session_id,
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        status="in_progress",
    )
    db.add(session)

    question_rows: list[SessionQuestion] = []
    for idx, question in enumerate(selected_questions, start=1):
        row = SessionQuestion(
            session_id=session_id,
            question_id=question["id"],
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            question_text=question["text"],
            topic=question.get("topic", "General"),
            question_type=question.get("type", "fixed"),
            order_index=idx,
        )
        question_rows.append(row)
        db.add(row)

    db.commit()

    return {
        "session_id": session_id,
        "candidate_id": candidate_id,
        "status": "in_progress",
        "questions": [
            {
                "question_id": q.question_id,
                "question_text": q.question_text,
                "topic": q.topic,
                "question_type": q.question_type,
                "order_index": q.order_index,
            }
            for q in question_rows
        ],
    }


@router.post("/responses/upload", response_model=UploadResponseOut)
async def upload_candidate_response(
    session_id: str = Form(...),
    question_id: str = Form(...),
    duration_seconds: float | None = Form(default=None),
    transcript_hint: str | None = Form(default=None),
    media_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    session = db.scalar(select(CandidateSession).where(CandidateSession.id == session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _ensure_session_access(session, current_user)

    question = db.scalar(
        select(SessionQuestion).where(
            SessionQuestion.session_id == session_id,
            SessionQuestion.question_id == question_id,
        )
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found for session")

    existing = db.scalar(
        select(CandidateResponse).where(
            CandidateResponse.session_id == session_id,
            CandidateResponse.question_id == question_id,
        )
    )
    if existing:
        if not existing.candidate_name or not existing.candidate_email:
            candidate_name, candidate_email = _resolve_session_candidate_identity(db=db, session=session)
            existing.candidate_name = existing.candidate_name or candidate_name
            existing.candidate_email = existing.candidate_email or candidate_email
            db.commit()

        auto_evaluated = _schedule_session_evaluation_if_ready(
            db=db,
            session=session,
        )

        return {
            "response_id": existing.id,
            "question_id": existing.question_id,
            "transcript": existing.transcript or "",
            "uploaded_at": _as_utc(existing.created_at),
            "auto_evaluated": auto_evaluated,
        }

    media_path, file_name, mime = await storage_service.store_media(
        session_id=session_id,
        question_id=question_id,
        upload_file=media_file,
    )
    candidate_name, candidate_email = _resolve_session_candidate_identity(db=db, session=session)

    response = CandidateResponse(
        session_id=session_id,
        question_id=question_id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        media_filename=file_name,
        media_mime=mime,
        media_blob=None,
        media_path=media_path,
        duration_seconds=duration_seconds,
        transcript=TranscriptionService.clean_text(transcript_hint) or None,
        created_at=datetime.now(timezone.utc),
    )

    db.add(response)
    db.commit()
    db.refresh(response)

    auto_evaluated = _schedule_session_evaluation_if_ready(
        db=db,
        session=session,
    )

    return {
        "response_id": response.id,
        "question_id": response.question_id,
        "transcript": response.transcript or "",
        "uploaded_at": _as_utc(response.created_at),
        "auto_evaluated": auto_evaluated,
    }


@router.get(
    "/sessions/{session_id}/questions/{question_id}/upload-status",
    response_model=UploadStatusOut,
)
def get_question_upload_status(
    session_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    session = db.scalar(select(CandidateSession).where(CandidateSession.id == session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _ensure_session_access(session, current_user)

    response = db.scalar(
        select(CandidateResponse)
        .where(
            CandidateResponse.session_id == session_id,
            CandidateResponse.question_id == question_id,
        )
        .order_by(CandidateResponse.created_at.desc())
    )

    return {
        "session_id": session_id,
        "question_id": question_id,
        "uploaded": response is not None,
        "response_id": response.id if response else None,
        "uploaded_at": _as_utc(response.created_at) if response else None,
    }


@router.post("/admin/sessions/{session_id}/evaluate", response_model=EvaluationSummaryOut)
def admin_evaluate_session(
    session_id: str,
    db: Session = Depends(get_db),
):
    try:
        return _get_evaluation_service().evaluate_session(db=db, session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {exc}") from exc


@router.get("/sessions/{session_id}", response_model=SessionProgressOut)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    session = db.scalar(select(CandidateSession).where(CandidateSession.id == session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _ensure_session_access(session, current_user)

    questions = db.scalars(
        select(SessionQuestion)
        .where(SessionQuestion.session_id == session_id)
        .order_by(SessionQuestion.order_index.asc())
    ).all()

    completed = db.scalar(
        select(func.count(func.distinct(CandidateResponse.question_id))).where(
            CandidateResponse.session_id == session_id
        )
    ) or 0

    return {
        "session_id": session.id,
        "candidate_id": session.candidate_id,
        "status": session.status,
        "total_questions": len(questions),
        "completed_answers": int(completed),
        "questions": [
            {
                "question_id": q.question_id,
                "question_text": q.question_text,
                "topic": q.topic,
                "question_type": q.question_type,
                "order_index": q.order_index,
            }
            for q in questions
        ],
    }


@router.get("/admin/results", response_model=list[AdminResultOut])
def list_admin_results(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    pending_session_ids = db.scalars(
        select(CandidateSession.id)
        .where(
            CandidateSession.status == "submitted",
            CandidateSession.overall_score.is_(None),
        )
        .order_by(CandidateSession.created_at.desc())
        .limit(20)
    ).all()
    for session_id in pending_session_ids:
        _enqueue_session_evaluation(session_id)

    latest_response_subquery = (
        select(
            CandidateResponse.session_id.label("session_id"),
            func.max(CandidateResponse.created_at).label("submitted_at"),
        )
        .group_by(CandidateResponse.session_id)
        .subquery()
    )

    rows = db.execute(
        select(
            CandidateSession.id.label("session_id"),
            User.unique_id.label("candidate_id"),
            User.name.label("user_name"),
            User.email.label("user_email"),
            CandidateSession.candidate_name.label("session_candidate_name"),
            CandidateSession.candidate_id.label("session_candidate_email"),
            CandidateSession.overall_score.label("final_score"),
            CandidateSession.status_label.label("status_label"),
            CandidateSession.created_at.label("created_at"),
            func.coalesce(
                CandidateSession.evaluated_at,
                latest_response_subquery.c.submitted_at,
            ).label("submitted_at"),
            CandidateSession.communication_total.label("communication_total"),
            CandidateSession.content_total.label("content_total"),
            CandidateSession.confidence_total.label("confidence_total"),
            select(func.count())
            .select_from(SessionQuestion)
            .where(SessionQuestion.session_id == CandidateSession.id)
            .scalar_subquery()
            .label("question_count"),
        )
        .outerjoin(User, User.email == CandidateSession.candidate_id)
        .outerjoin(
            latest_response_subquery,
            latest_response_subquery.c.session_id == CandidateSession.id,
        )
        .order_by(CandidateSession.created_at.desc())
        .limit(limit)
    ).all()

    return [
        {
            "session_id": row.session_id,
            "candidate_id": row.candidate_id or "",
            "candidate_name": _resolve_candidate_name(
                row.session_candidate_name or row.user_name,
                row.user_email or row.session_candidate_email or ""
            ),
            "candidate_email": row.user_email or row.session_candidate_email or "",
            "final_score": row.final_score,
            "status_label": row.status_label,
            "created_at": _as_utc(row.created_at),
            "submitted_at": _as_utc(row.submitted_at),
            "communication_avg": (
                (float(row.communication_total) / (max(int(row.question_count or 0), 1) * 10.0)) * 10.0
                if (row.communication_total is not None and row.final_score is not None)
                else None
            ),
            "content_avg": (
                (float(row.content_total) / (max(int(row.question_count or 0), 1) * 10.0)) * 10.0
                if (row.content_total is not None and row.final_score is not None)
                else None
            ),
            "confidence_avg": (
                (float(row.confidence_total) / (max(int(row.question_count or 0), 1) * 10.0)) * 10.0
                if (row.confidence_total is not None and row.final_score is not None)
                else None
            ),
        }
        for row in rows
    ]


@router.get("/admin/sessions/{session_id}", response_model=AdminSessionDetailOut)
def get_admin_session_detail(
    session_id: str,
    db: Session = Depends(get_db),
):
    session = db.scalar(select(CandidateSession).where(CandidateSession.id == session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "submitted" and session.overall_score is None:
        _enqueue_session_evaluation(session_id)

    lookup_key = (session.candidate_id or "").strip().lower()
    user = None
    if lookup_key:
        user = db.scalar(select(User).where(User.email == lookup_key))
    candidate_email = (session.candidate_email or (user.email if user else lookup_key) or "").strip().lower()
    candidate_name = _resolve_candidate_name(
        session.candidate_name or (user.name if user else None),
        candidate_email,
    )

    questions = db.scalars(
        select(SessionQuestion)
        .where(SessionQuestion.session_id == session_id)
        .order_by(SessionQuestion.order_index.asc())
    ).all()

    responses = db.scalars(
        select(CandidateResponse)
        .where(CandidateResponse.session_id == session_id)
        .order_by(CandidateResponse.created_at.asc())
    ).all()

    response_by_question: dict[str, CandidateResponse] = {}
    for response in responses:
        response_by_question[response.question_id] = response

    submitted_at = session.evaluated_at
    if not submitted_at and responses:
        submitted_at = max(r.created_at for r in responses)

    response_items: list[dict] = []
    communication_scores = []
    content_scores = []
    confidence_scores = []
    
    for question in questions:
        response = response_by_question.get(question.question_id)
        if not response:
            continue

        response_items.append(
            {
                "response_id": response.id,
                "question_id": question.question_id,
                "question_text": question.question_text,
                "order_index": question.order_index,
                "transcript": response.transcript or "",
                "communication_score": response.communication_score,
                "content_score": response.content_score,
                "confidence_score": response.confidence_score,
                "final_score": response.final_score,
                "feedback": None,
                "strengths": [],
                "weaknesses": [],
                "media_url": f"/api/admin/sessions/{session_id}/responses/{response.id}/media",
                "uploaded_at": _as_utc(response.created_at),
            }
        )
        
        # Collect scores for averaging
        if response.communication_score is not None:
            communication_scores.append(response.communication_score)
        if response.content_score is not None:
            content_scores.append(response.content_score)
        if response.confidence_score is not None:
            confidence_scores.append(response.confidence_score)
    
    communication_avg = None
    content_avg = None
    confidence_avg = None

    question_scale = max(len(questions), 1) * 10.0
    if session.communication_total is not None:
        communication_avg = (float(session.communication_total) / question_scale) * 10.0
    elif communication_scores:
        communication_avg = (sum(communication_scores) / question_scale) * 10.0

    if session.content_total is not None:
        content_avg = (float(session.content_total) / question_scale) * 10.0
    elif content_scores:
        content_avg = (sum(content_scores) / question_scale) * 10.0

    if session.confidence_total is not None:
        confidence_avg = (float(session.confidence_total) / question_scale) * 10.0
    elif confidence_scores:
        confidence_avg = (sum(confidence_scores) / question_scale) * 10.0

    return {
        "session_id": session.id,
        "candidate_id": user.unique_id if user else "",
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "final_score": session.overall_score,
        "status_label": session.status_label,
        "created_at": _as_utc(session.created_at),
        "submitted_at": _as_utc(submitted_at),
        "question_count": len(questions),
        "responses": response_items,
        "communication_avg": communication_avg,
        "content_avg": content_avg,
        "confidence_avg": confidence_avg,
    }


@router.get("/admin/sessions/{session_id}/responses/{response_id}/media")
def get_admin_response_media(
    session_id: str,
    response_id: int,
    db: Session = Depends(get_db),
):
    response = db.scalar(
        select(CandidateResponse).where(
            CandidateResponse.id == response_id,
            CandidateResponse.session_id == session_id,
        )
    )
    if not response:
        raise HTTPException(status_code=404, detail="Response media not found")

    path = Path(response.media_path)
    if path.exists():
        return FileResponse(
            path=path,
            media_type=response.media_mime,
            filename=response.media_filename,
        )

    if response.media_blob:
        return Response(
            content=response.media_blob,
            media_type=response.media_mime,
            headers={"Content-Disposition": f'inline; filename="{response.media_filename}"'},
        )

    raise HTTPException(status_code=404, detail="Media file not found")


@router.delete("/admin/sessions/{session_id}", response_model=AdminDeleteOut)
def delete_admin_session(
    session_id: str,
    db: Session = Depends(get_db),
):
    session = db.scalar(select(CandidateSession).where(CandidateSession.id == session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    responses = db.scalars(
        select(CandidateResponse).where(CandidateResponse.session_id == session_id)
    ).all()
    media_paths = [r.media_path for r in responses if r.media_path]

    db.delete(session)
    db.commit()

    mysql_sync_service.delete_session(session_id)

    for media_path in media_paths:
        try:
            Path(media_path).unlink(missing_ok=True)
        except Exception:
            continue

    return {
        "session_id": session_id,
        "deleted": True,
    }
