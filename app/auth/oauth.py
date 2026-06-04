"""
Google OAuth2 flow — multi-user, Postgres-backed.

Token flow:
  1. /auth/login        → redirect to Google
  2. /auth/callback     → upsert user, save Google creds, redirect to
                          /auth/success?token=<5-min exchange token>
  3. background.ts      → intercepts URL, POSTs exchange token to /auth/exchange
  4. /auth/exchange     → validates exchange token, returns 7-day session token
  5. background.ts      → stores session token in chrome.storage.local

Token refresh:
  - /auth/refresh       → accepts expired session token (24h grace), checks Google
                          refresh token is still valid, returns new session token
"""
import logging
import os
from typing import Optional

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.session import (
    _decode_token,
    _extract_bearer,
    create_access_token,
    create_exchange_token,
)
from app.auth.token_store import save_token
from app.db.database import get_pg_db
from app.db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "openid",
    "email",
    "profile",
]
REDIRECT_URI_DEFAULT = "http://localhost:8000/auth/callback"

# In-process state store (fine for single-server dev; use Redis for multi-instance)
_pending_flows: dict[str, Flow] = {}


def _make_flow() -> Flow:
    redirect_uri = os.getenv("GMAIL_REDIRECT_URI", REDIRECT_URI_DEFAULT)
    secrets_file = os.getenv("GMAIL_CLIENT_SECRETS_FILE", "gmail-client-secret.json")

    if os.path.exists(secrets_file):
        flow = Flow.from_client_secrets_file(secrets_file, scopes=GMAIL_SCOPES)
    else:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": os.getenv("GMAIL_CLIENT_ID"),
                    "client_secret": os.getenv("GMAIL_CLIENT_SECRET"),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=GMAIL_SCOPES,
        )
    flow.redirect_uri = redirect_uri
    return flow


@router.get("/login")
def auth_login():
    """Start the Google OAuth2 flow."""
    flow = _make_flow()
    auth_url, state = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true",
    )
    _pending_flows[state] = flow
    return RedirectResponse(auth_url)


@router.get("/callback")
def auth_callback(code: str, state: str = "", db: Session = Depends(get_pg_db)):
    """Exchange Google code → upsert user → redirect with a 5-min exchange token."""
    flow = _pending_flows.pop(state, None) or _make_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    import google.auth.transport.requests as g_req
    import requests as req_lib

    google_req = g_req.Request(session=req_lib.Session())
    creds.refresh(google_req)

    userinfo_res = req_lib.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"},
    )
    userinfo = userinfo_res.json()
    google_sub = userinfo.get("sub")
    email = userinfo.get("email", "")
    name = userinfo.get("name", "")

    user = db.query(User).filter(User.google_sub == google_sub).first()
    if user is None:
        user = User(google_sub=google_sub, email=email, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.email = email
        user.name = name
        db.commit()

    save_token(db, user, creds)

    # Short-lived exchange token in URL — background.ts swaps it for a session token
    # via POST /auth/exchange before the 5-min window closes.
    exchange = create_exchange_token(user.id)
    logger.info("User authenticated: %s (id=%s)", email, user.id)
    return RedirectResponse(url=f"/auth/success?token={exchange}")


@router.get("/success")
def auth_success(token: str = ""):
    """
    Landing page after OAuth. background.ts detects this URL, POSTs the token
    to /auth/exchange, stores the returned session token, then closes this tab.
    """
    return {
        "status": "authenticated",
        "message": "Gmail authenticated. You can close this tab and return to the extension.",
    }


class ExchangeRequest(BaseModel):
    code: str


@router.post("/exchange")
def auth_exchange(body: ExchangeRequest, db: Session = Depends(get_pg_db)):
    """Swap a 5-minute exchange token for a 7-day session token.

    Called by background.ts immediately after the OAuth redirect.
    Exchange tokens are short-lived and type-locked so they can't be reused
    as session tokens even if the URL leaks.
    """
    user_id = _decode_token(body.code, token_type="exchange")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired exchange code")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return {"access_token": create_access_token(user_id)}


@router.post("/refresh")
def auth_refresh(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_pg_db),
):
    """Issue a new session token if the Google refresh token is still valid.

    Accepts an expired session token (up to 24h past expiry).
    If the Google refresh token is itself expired, returns 401 and the
    frontend clears storage to force a full re-login.
    """
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No token provided")

    user_id = _decode_token(token, token_type="session", verify_exp=False)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Verify the Google refresh token is still valid by attempting a proactive refresh
    try:
        from google.auth.transport.requests import Request
        from app.auth.token_store import get_credentials
        creds = get_credentials(db, user_id)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_token(db, user, creds)
        elif not creds.refresh_token:
            raise ValueError("No refresh token stored")
    except Exception as exc:
        logger.warning("Google credential refresh failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google session expired — please sign in again",
        )

    return {"access_token": create_access_token(user_id)}


@router.post("/logout")
def auth_logout():
    """Client-side logout: the extension deletes its chrome.storage.local token."""
    return {"status": "logged out"}
