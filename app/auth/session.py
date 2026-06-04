"""
JWT-based auth via Authorization: Bearer header.
Token is stored in chrome.storage.local by the extension background script.

Two token types:
  exchange  (5 min)  — placed in OAuth redirect URL, single-use, exchanged for session token
  session   (7 days) — stored in chrome.storage.local, sent on every API call
"""
import datetime
import os
from typing import Optional

from jose import JWTError, jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_pg_db
from app.db.models import User

SECRET_KEY = os.environ.get("JWT_SECRET", "dev-secret-change-me")
ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "168"))


def create_access_token(user_id: int) -> str:
    """7-day session token stored in chrome.storage.local."""
    expire = datetime.datetime.utcnow() + datetime.timedelta(hours=EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "session"},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def create_exchange_token(user_id: int) -> str:
    """5-minute one-time token placed in the OAuth redirect URL.
    Background script calls /auth/exchange to swap it for a session token.
    Short expiry limits the window where the URL in browser history is dangerous.
    """
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "exchange"},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def _decode_token(
    token: str,
    token_type: str = "session",
    verify_exp: bool = True,
) -> Optional[int]:
    """Decode a JWT and return user_id, or None if invalid.

    token_type: "session" | "exchange" — tokens of the wrong type are rejected.
    verify_exp=False: used by /auth/refresh to decode expired session tokens
                      within a 24-hour grace window.
    """
    try:
        options = {"verify_exp": verify_exp}
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options=options)

        # Tokens issued before type claim was added default to "session"
        claimed_type = payload.get("type", "session")
        if claimed_type != token_type:
            return None

        # Grace-period guard: reject tokens older than 24h even with verify_exp=False
        if not verify_exp:
            exp = payload.get("exp")
            if exp:
                age_hours = (datetime.datetime.utcnow().timestamp() - exp) / 3600
                if age_hours > 24:
                    return None

        user_id = payload.get("sub")
        return int(user_id) if user_id else None
    except JWTError:
        return None


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_pg_db),
) -> User:
    """FastAPI dependency: validates Bearer session token and returns the User row."""
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = _decode_token(token, token_type="session")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_optional_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_pg_db),
) -> Optional[User]:
    """Like get_current_user but returns None instead of raising 401."""
    token = _extract_bearer(authorization)
    if not token:
        return None
    user_id = _decode_token(token, token_type="session")
    if user_id is None:
        return None
    return db.query(User).filter(User.id == user_id).first()
