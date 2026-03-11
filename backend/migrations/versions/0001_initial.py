"""Initial schema.

Revision ID: 0001_initial
Revises: 
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("unique_id", sa.String(length=64), nullable=False),
        sa.Column("candidate_id", sa.String(length=320), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("unique_id", name="uq_users_unique_id"),
        sa.UniqueConstraint("candidate_id", name="uq_users_candidate_id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_unique_id", "users", ["unique_id"])
    op.create_index("ix_users_candidate_id", "users", ["candidate_id"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "candidate_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("candidate_id", sa.String(length=320), nullable=False),
        sa.Column("candidate_name", sa.String(length=255), nullable=True),
        sa.Column("candidate_email", sa.String(length=320), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=True),
        sa.Column("status_label", sa.String(length=24), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_candidate_sessions_id", "candidate_sessions", ["id"])
    op.create_index("ix_candidate_sessions_candidate_id", "candidate_sessions", ["candidate_id"])
    op.create_index("idx_candidate_sessions_created_at", "candidate_sessions", ["created_at"])

    op.create_table(
        "session_questions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=32), nullable=False),
        sa.Column("candidate_name", sa.String(length=255), nullable=True),
        sa.Column("candidate_email", sa.String(length=320), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=80), nullable=False),
        sa.Column("question_type", sa.String(length=24), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["candidate_sessions.id"]),
        sa.UniqueConstraint("session_id", "question_id", name="uq_session_question"),
    )
    op.create_index("ix_session_questions_session_id", "session_questions", ["session_id"])
    op.create_index("ix_session_questions_question_id", "session_questions", ["question_id"])

    op.create_table(
        "candidate_responses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=32), nullable=False),
        sa.Column("candidate_name", sa.String(length=255), nullable=True),
        sa.Column("candidate_email", sa.String(length=320), nullable=True),
        sa.Column("media_filename", sa.String(length=255), nullable=False),
        sa.Column("media_mime", sa.String(length=120), nullable=True),
        sa.Column("media_blob", sa.LargeBinary(), nullable=True),
        sa.Column("media_path", sa.String(length=500), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["candidate_sessions.id"]),
        sa.UniqueConstraint("session_id", "question_id", name="uq_response_question"),
    )
    op.create_index("ix_candidate_responses_session_id", "candidate_responses", ["session_id"])
    op.create_index("ix_candidate_responses_question_id", "candidate_responses", ["question_id"])
    op.create_index(
        "idx_candidate_responses_session_created",
        "candidate_responses",
        ["session_id", "created_at"],
    )
    op.create_index(
        "idx_candidate_responses_session_question",
        "candidate_responses",
        ["session_id", "question_id"],
    )

    op.create_table(
        "scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=320), nullable=False),
        sa.Column("candidate_name", sa.String(length=255), nullable=True),
        sa.Column("candidate_email", sa.String(length=320), nullable=True),
        sa.Column("ai_communication_score", sa.Float(), nullable=True),
        sa.Column("ai_content_score", sa.Float(), nullable=True),
        sa.Column("ai_confidence_score", sa.Float(), nullable=True),
        sa.Column("ai_total_score", sa.Float(), nullable=True),
        sa.Column("evaluator_communication_score", sa.Float(), nullable=True),
        sa.Column("evaluator_content_score", sa.Float(), nullable=True),
        sa.Column("evaluator_confidence_score", sa.Float(), nullable=True),
        sa.Column("evaluator_total_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["candidate_sessions.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["users.candidate_id"]),
        sa.UniqueConstraint("session_id", name="uq_scores_session"),
    )
    op.create_index("ix_scores_session_id", "scores", ["session_id"])
    op.create_index("ix_scores_candidate_id", "scores", ["candidate_id"])


def downgrade() -> None:
    op.drop_index("ix_scores_candidate_id", table_name="scores")
    op.drop_index("ix_scores_session_id", table_name="scores")
    op.drop_table("scores")

    op.drop_index("idx_candidate_responses_session_question", table_name="candidate_responses")
    op.drop_index("idx_candidate_responses_session_created", table_name="candidate_responses")
    op.drop_index("ix_candidate_responses_question_id", table_name="candidate_responses")
    op.drop_index("ix_candidate_responses_session_id", table_name="candidate_responses")
    op.drop_table("candidate_responses")

    op.drop_index("ix_session_questions_question_id", table_name="session_questions")
    op.drop_index("ix_session_questions_session_id", table_name="session_questions")
    op.drop_table("session_questions")

    op.drop_index("idx_candidate_sessions_created_at", table_name="candidate_sessions")
    op.drop_index("ix_candidate_sessions_candidate_id", table_name="candidate_sessions")
    op.drop_index("ix_candidate_sessions_id", table_name="candidate_sessions")
    op.drop_table("candidate_sessions")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_candidate_id", table_name="users")
    op.drop_index("ix_users_unique_id", table_name="users")
    op.drop_table("users")
