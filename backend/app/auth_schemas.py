from datetime import datetime

from pydantic import BaseModel, EmailStr


class SessionUserOut(BaseModel):
    unique_id: str
    email: EmailStr
    provider: str
    created_at: datetime | None = None


class AuthMessageOut(BaseModel):
    message: str
