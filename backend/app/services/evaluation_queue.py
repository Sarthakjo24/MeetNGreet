from redis import Redis
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job
from opentelemetry.propagate import inject

from ..config import settings


def _get_redis() -> Redis:
    return Redis.from_url(settings.redis_url)


def _get_queue() -> Queue:
    return Queue(
        name=settings.evaluation_queue_name,
        connection=_get_redis(),
        default_timeout=settings.evaluation_job_timeout,
    )


def enqueue_session_evaluation(session_id: str) -> bool:
    queue = _get_queue()
    job_id = f"eval:{session_id}"
    try:
        job = Job.fetch(job_id, connection=queue.connection)
        status = job.get_status()
        if status in {"queued", "started", "deferred", "scheduled"}:
            return False
        job.delete()
    except NoSuchJobError:
        pass

    trace_context: dict[str, str] = {}
    try:
        inject(trace_context)
    except Exception:
        trace_context = {}

    queue.enqueue(
        "backend.app.workers.evaluation_worker.evaluate_session_job",
        session_id,
        job_id=job_id,
        description=f"Evaluate session {session_id}",
        result_ttl=0,
        ttl=settings.evaluation_job_ttl,
        failure_ttl=settings.evaluation_failure_ttl,
        meta={"trace_context": trace_context} if trace_context else None,
    )
    return True
