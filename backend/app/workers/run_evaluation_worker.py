import multiprocessing as mp
import os

from redis import Redis
from rq import Connection, Worker

from ..config import settings
from ..logging_config import configure_logging
from ..telemetry import configure_telemetry
from ..services.evaluation_requeue import run_requeue_loop


def _run_worker() -> None:
    configure_logging()
    configure_telemetry()
    redis_conn = Redis.from_url(settings.redis_url)
    with Connection(redis_conn):
        worker = Worker([settings.evaluation_queue_name])
        worker.work(logging_level="INFO")


def _run_requeue() -> None:
    configure_logging()
    configure_telemetry()
    run_requeue_loop()


def main() -> None:
    cpu_count = os.cpu_count() or 1
    worker_count = max(1, min(settings.evaluation_max_workers, cpu_count))
    processes: list[mp.Process] = []

    if settings.evaluation_requeue_enabled:
        requeue_process = mp.Process(target=_run_requeue, name="eval-requeue")
        requeue_process.start()
        processes.append(requeue_process)

    for idx in range(worker_count):
        process = mp.Process(target=_run_worker, name=f"eval-worker-{idx + 1}")
        process.start()
        processes.append(process)

    for process in processes:
        process.join()


if __name__ == "__main__":
    mp.freeze_support()
    main()
