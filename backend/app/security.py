from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, HTTPException
from jose import JWTError, jwt

from .config import settings


@dataclass
class CurrentUser:
    unique_id: str
    email: str
    provider: str


def create_session_token(user: CurrentUser) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.session_ttl_minutes)
    payload = {
        "sub": user.unique_id,
        "email": user.email,
        "provider": user.provider,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.session_secret, algorithm=settings.session_algorithm)


def decode_session_token(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(
            token,
            settings.session_secret,
            algorithms=[settings.session_algorithm],
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid session token.") from exc

    unique_id = payload.get("sub")
    email = payload.get("email")
    provider = payload.get("provider")
    if not unique_id or not email or not provider:
        raise HTTPException(status_code=401, detail="Invalid session payload.")

    return CurrentUser(
        unique_id=str(unique_id),
        email=str(email),
        provider=str(provider),
    )


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> CurrentUser:
    if not session_token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return decode_session_token(session_token)
