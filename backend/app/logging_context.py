from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
job_id_var: ContextVar[str | None] = ContextVar("job_id", default=None)
session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()


def get_job_id() -> str | None:
    return job_id_var.get()


def get_session_id() -> str | None:
    return session_id_var.get()


@contextmanager
def bind_log_context(
    *,
    request_id: str | None = None,
    job_id: str | None = None,
    session_id: str | None = None,
):
    tokens: list[tuple[ContextVar[str | None], object]] = []
    try:
        if request_id is not None:
            tokens.append((request_id_var, request_id_var.set(request_id)))
        if job_id is not None:
            tokens.append((job_id_var, job_id_var.set(job_id)))
        if session_id is not None:
            tokens.append((session_id_var, session_id_var.set(session_id)))
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
