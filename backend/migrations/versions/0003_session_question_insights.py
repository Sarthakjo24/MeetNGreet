"""Add per-question feedback/insight columns to session_questions.

Revision ID: 0003_session_question_insights
Revises: 0002_session_question_scores
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0003_session_question_insights"
down_revision = "0002_session_question_scores"
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
        ("Candidate_strengths", sa.Text()),
        ("Candidate_weakness", sa.Text()),
        ("Candidate_feedback", sa.Text()),
    ]

    for name, col_type in columns:
        if not _has_column(inspector, "session_questions", name):
            op.add_column("session_questions", sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = [
        "Candidate_feedback",
        "Candidate_weakness",
        "Candidate_strengths",
    ]

    for name in columns:
        if _has_column(inspector, "session_questions", name):
            op.drop_column("session_questions", name)
