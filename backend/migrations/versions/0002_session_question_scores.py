"""Add per-question score columns to session_questions.

Revision ID: 0002_session_question_scores
Revises: 0001_initial
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0002_session_question_scores"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    try:
        return any(col["name"] == column_name for col in inspector.get_columns(table_name))
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = [
        ("Question_Communication_score", sa.Float()),
        ("Question_content_score", sa.Float()),
        ("Question_confidence_score", sa.Float()),
        ("Question_total_score", sa.Float()),
    ]

    for name, col_type in columns:
        if not _has_column(inspector, "session_questions", name):
            op.add_column("session_questions", sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = [
        "Question_total_score",
        "Question_confidence_score",
        "Question_content_score",
        "Question_Communication_score",
    ]

    for name in columns:
        if _has_column(inspector, "session_questions", name):
            op.drop_column("session_questions", name)
