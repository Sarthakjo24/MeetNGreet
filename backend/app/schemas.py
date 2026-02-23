from datetime import datetime

from pydantic import BaseModel, Field


class QuestionOut(BaseModel):
    question_id: str
    question_text: str
    topic: str
    question_type: str
    order_index: int


class CandidateSessionOut(BaseModel):
    session_id: str
    candidate_id: str
    status: str
    questions: list[QuestionOut]


class UploadResponseOut(BaseModel):
    response_id: int
    question_id: str
    transcript: str
    uploaded_at: datetime
    auto_evaluated: bool = False


class UploadStatusOut(BaseModel):
    session_id: str
    question_id: str
    uploaded: bool
    response_id: int | None = None
    uploaded_at: datetime | None = None


class QuestionEvaluationOut(BaseModel):
    question_id: str
    communication_score: float
    content_score: float
    confidence_score: float
    final_score: float
    feedback: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class EvaluationSummaryOut(BaseModel):
    session_id: str
    candidate_id: str
    final_score: float
    status_label: str
    question_results: list[QuestionEvaluationOut]


class SessionProgressOut(BaseModel):
    session_id: str
    candidate_id: str
    status: str
    total_questions: int
    completed_answers: int
    questions: list[QuestionOut]


class AdminResultOut(BaseModel):
    session_id: str
    candidate_id: str
    candidate_email: str
    final_score: float | None
    status_label: str | None
    created_at: datetime
    submitted_at: datetime | None


class AdminQuestionResponseOut(BaseModel):
    response_id: int
    question_id: str
    question_text: str
    order_index: int
    transcript: str
    communication_score: float | None
    content_score: float | None
    confidence_score: float | None
    final_score: float | None
    feedback: str | None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    media_url: str
    uploaded_at: datetime


class AdminSessionDetailOut(BaseModel):
    session_id: str
    candidate_id: str
    candidate_email: str
    final_score: float | None
    status_label: str | None
    created_at: datetime
    submitted_at: datetime | None
    question_count: int
    responses: list[AdminQuestionResponseOut]


class AdminDeleteOut(BaseModel):
    session_id: str
    deleted: bool
