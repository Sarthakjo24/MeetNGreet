from redis import Redis
from rq import Queue
from rq.registry import FailedJobRegistry

from ..config import settings


def get_failed_job_count() -> int:
    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue(name=settings.evaluation_queue_name, connection=redis_conn)
    registry = FailedJobRegistry(queue=queue)
    return registry.count
