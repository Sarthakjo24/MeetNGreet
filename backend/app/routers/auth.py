import hashlib
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth_schemas import AuthMessageOut, SessionUserOut
from ..config import settings
from ..database import get_db
from ..models import User
from ..security import (
    CurrentUser,
    create_session_token,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _cookie_kwargs(max_age_seconds: int | None = None) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite,
        "path": "/",
    }
    if settings.session_cookie_domain:
        kwargs["domain"] = settings.session_cookie_domain
    if max_age_seconds is not None:
        kwargs["max_age"] = max_age_seconds
    return kwargs


def _safe_next_path(next_path: str | None) -> str:
    if not next_path:
        return "/interview"
    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/interview"
    return next_path


def _stable_unique_id(seed: str) -> str:
    normalized = (seed or "").strip()
    if normalized and len(normalized) <= 64:
        return normalized
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:64]


def _issue_session_cookie(response: Response, user: User) -> None:
    token = create_session_token(
        CurrentUser(
            unique_id=user.unique_id,
            email=user.email,
            provider=user.provider,
        )
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        **_cookie_kwargs(max_age_seconds=settings.session_ttl_minutes * 60),
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        domain=settings.session_cookie_domain,
    )


def _require_auth0_config() -> None:
    if not settings.auth0_domain or not settings.auth0_client_id or not settings.auth0_client_secret:
        raise HTTPException(status_code=500, detail="Auth0 credentials are missing in .env.")


def _auth0_base_url() -> str:
    _require_auth0_config()
    return f"https://{settings.auth0_domain}"


def _auth0_connection_from_provider(provider: str) -> str:
    if provider == "google":
        return settings.auth0_google_connection
    if provider == "microsoft":
        return settings.auth0_microsoft_connection
    raise HTTPException(status_code=400, detail="Unsupported SSO provider.")


def _verify_auth0_id_token(id_token: str) -> dict:
    base_url = _auth0_base_url()
    jwks_response = requests.get(f"{base_url}/.well-known/jwks.json", timeout=10)
    jwks_response.raise_for_status()
    jwks = jwks_response.json()

    try:
        unverified_header = jwt.get_unverified_header(id_token)
    except JWTError as exc:
        raise HTTPException(status_code=400, detail="Invalid Auth0 token header.") from exc

    kid = unverified_header.get("kid")
    key = None
    for candidate in jwks.get("keys", []):
        if candidate.get("kid") == kid:
            key = candidate
            break

    if not key:
        raise HTTPException(status_code=400, detail="Auth0 token key not found.")

    issuer = f"{base_url}/"
    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=settings.auth0_client_id,
            issuer=issuer,
        )
    except JWTError as exc:
        raise HTTPException(status_code=400, detail="Invalid Auth0 id_token.") from exc

    return claims


@router.get("/session", response_model=SessionUserOut)
def session(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.unique_id == current_user.unique_id))
    if not user:
        raise HTTPException(status_code=401, detail="Session user not found.")

    return {
        "unique_id": user.unique_id,
        "email": user.email,
        "provider": user.provider,
        "created_at": user.created_at,
    }


@router.post("/logout", response_model=AuthMessageOut)
def logout(response: Response):
    _clear_session_cookie(response)
    return {"message": "Logged out successfully."}


@router.get("/auth0/login")
def auth0_login(
    provider: str = Query(..., pattern="^(google|microsoft)$"),
    next_path: str | None = Query(default="/interview", alias="next"),
    login_hint: str | None = Query(default=None),
):
    base_url = _auth0_base_url()
    connection = _auth0_connection_from_provider(provider)
    state = secrets.token_urlsafe(24)
    safe_next = _safe_next_path(next_path)

    query = {
        "response_type": "code",
        "client_id": settings.auth0_client_id,
        "redirect_uri": settings.auth0_callback_url,
        "scope": "openid profile email",
        "state": state,
        "connection": connection,
    }
    if login_hint:
        query["login_hint"] = login_hint.strip()

    auth_url = f"{base_url}/authorize?{urlencode(query)}"

    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie("oauth_state", state, **_cookie_kwargs(max_age_seconds=600))
    response.set_cookie("oauth_provider", provider, **_cookie_kwargs(max_age_seconds=600))
    response.set_cookie("oauth_next", safe_next, **_cookie_kwargs(max_age_seconds=600))
    return response


@router.get("/google")
def google_login(
    next_path: str | None = Query(default="/interview", alias="next"),
    login_hint: str | None = Query(default=None),
):
    return auth0_login(provider="google", next_path=next_path, login_hint=login_hint)


@router.get("/microsoft")
def microsoft_login(
    next_path: str | None = Query(default="/interview", alias="next"),
    login_hint: str | None = Query(default=None),
):
    return auth0_login(provider="microsoft", next_path=next_path, login_hint=login_hint)


@router.get("/callback")
def auth0_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
    oauth_state: str | None = Cookie(default=None),
    oauth_provider: str | None = Cookie(default=None),
    oauth_next: str | None = Cookie(default=None),
):
    if not oauth_state or state != oauth_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state.")

    provider = oauth_provider or "google"
    safe_next = _safe_next_path(oauth_next)
    base_url = _auth0_base_url()

    token_response = requests.post(
        f"{base_url}/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": settings.auth0_client_id,
            "client_secret": settings.auth0_client_secret,
            "code": code,
            "redirect_uri": settings.auth0_callback_url,
        },
        timeout=15,
    )
    if token_response.status_code >= 400:
        raise HTTPException(status_code=400, detail="Failed to exchange Auth0 authorization code.")

    token_payload = token_response.json()
    id_token = token_payload.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="Missing id_token from Auth0 response.")

    claims = _verify_auth0_id_token(id_token)
    email = str(claims.get("email", "")).strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Auth0 did not return a valid email.")

    user = db.scalar(select(User).where(User.email == email))
    if not user:
        provider_subject = str(claims.get("sub") or f"{provider}:{email}")
        user = User(
            unique_id=_stable_unique_id(provider_subject),
            email=email,
            provider=provider,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.provider != provider:
        user.provider = provider
        db.commit()
        db.refresh(user)

    response = RedirectResponse(url=safe_next, status_code=302)
    _issue_session_cookie(response, user)
    response.delete_cookie("oauth_state", path="/", domain=settings.session_cookie_domain)
    response.delete_cookie("oauth_provider", path="/", domain=settings.session_cookie_domain)
    response.delete_cookie("oauth_next", path="/", domain=settings.session_cookie_domain)
    return response
