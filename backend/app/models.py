from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unique_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    candidate_id: Mapped[str | None] = mapped_column(String(320), unique=True, index=True, nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), default="google")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    scores: Mapped[list["Score"]] = relationship("Score", back_populates="user")


class CandidateSession(Base):
    __tablename__ = "candidate_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String(320), index=True)
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="in_progress")
    status_label: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    questions: Mapped[list["SessionQuestion"]] = relationship(
        "SessionQuestion",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    responses: Mapped[list["CandidateResponse"]] = relationship(
        "CandidateResponse",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    score: Mapped["Score | None"] = relationship(
        "Score",
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )


class SessionQuestion(Base):
    __tablename__ = "session_questions"
    __table_args__ = (UniqueConstraint("session_id", "question_id", name="uq_session_question"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("candidate_sessions.id"), index=True)
    question_id: Mapped[str] = mapped_column(String(32), index=True)
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    question_text: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(80))
    question_type: Mapped[str] = mapped_column(String(24), default="fixed")
    order_index: Mapped[int] = mapped_column(Integer)

    session: Mapped[CandidateSession] = relationship("CandidateSession", back_populates="questions")


class CandidateResponse(Base):
    __tablename__ = "candidate_responses"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "question_id",
            name="uq_response_question",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("candidate_sessions.id"), index=True)
    question_id: Mapped[str] = mapped_column(String(32), index=True)
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    media_filename: Mapped[str] = mapped_column(String(255))
    media_mime: Mapped[str] = mapped_column(String(120), default="video/webm")
    media_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    media_path: Mapped[str] = mapped_column(String(500))
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped[CandidateSession] = relationship("CandidateSession", back_populates="responses")


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            name="uq_scores_session",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("candidate_sessions.id"), index=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("users.candidate_id"), index=True)
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    ai_communication_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_content_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_total_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    evaluator_communication_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluator_content_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluator_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluator_total_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user: Mapped[User] = relationship("User", back_populates="scores")
    session: Mapped[CandidateSession] = relationship("CandidateSession", back_populates="score")
