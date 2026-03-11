import logging
import time
from datetime import datetime, timedelta

from redis import Redis
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import CandidateSession, Score
from .evaluation_queue import enqueue_session_evaluation

logger = logging.getLogger(__name__)

_LOCK_KEY = "eval:requeue:lock"


def _get_redis() -> Redis:
    return Redis.from_url(settings.redis_url)


def _acquire_lock(redis_conn: Redis) -> bool:
    ttl = max(5, settings.evaluation_requeue_lock_ttl_seconds)
    return bool(redis_conn.set(_LOCK_KEY, "1", nx=True, ex=ttl))


def _attempt_key(session_id: str) -> str:
    return f"eval:requeue:attempts:{session_id}"


def _should_skip_attempt(redis_conn: Redis, session_id: str) -> bool:
    max_attempts = max(1, settings.evaluation_requeue_max_attempts)
    raw = redis_conn.get(_attempt_key(session_id))
    if raw is None:
        return False
    try:
        count = int(raw)
    except (TypeError, ValueError):
        return False
    return count >= max_attempts


def _record_attempt(redis_conn: Redis, session_id: str) -> None:
    key = _attempt_key(session_id)
    count = redis_conn.incr(key)
    if count == 1:
        ttl = max(300, settings.evaluation_requeue_attempt_ttl_seconds)
        redis_conn.expire(key, ttl)


def _fetch_pending_sessions(db: Session) -> list[str]:
    cutoff = datetime.utcnow() - timedelta(minutes=1)
    rows = (
        db.execute(
            select(CandidateSession.id)
            .outerjoin(Score, Score.session_id == CandidateSession.id)
            .where(
                CandidateSession.status.in_(("submitted", "completed")),
                or_(Score.ai_total_score.is_(None), Score.id.is_(None)),
                CandidateSession.created_at <= cutoff,
            )
            .order_by(CandidateSession.created_at.asc())
            .limit(max(1, settings.evaluation_requeue_batch_size))
        )
        .scalars()
        .all()
    )
    return [str(row) for row in rows]


def requeue_pending_sessions() -> int:
    redis_conn = _get_redis()
    if not _acquire_lock(redis_conn):
        return 0

    enqueued = 0
    db = SessionLocal()
    try:
        session_ids = _fetch_pending_sessions(db)
        for session_id in session_ids:
            if _should_skip_attempt(redis_conn, session_id):
                continue
            if enqueue_session_evaluation(session_id):
                _record_attempt(redis_conn, session_id)
                enqueued += 1
    finally:
        db.close()
    return enqueued


def run_requeue_loop() -> None:
    interval = max(10, settings.evaluation_requeue_interval_seconds)
    while True:
        try:
            count = requeue_pending_sessions()
            if count:
                logger.info("Requeued %s pending evaluation jobs.", count)
        except Exception:
            logger.exception("Evaluation requeue loop failed.")
        time.sleep(interval)
