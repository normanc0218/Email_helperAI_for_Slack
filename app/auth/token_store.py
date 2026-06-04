"""
Encrypt/decrypt OAuth tokens before writing to Postgres.
Uses Fernet symmetric encryption (cryptography package).
"""
import datetime
import os
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.db.models import OAuthToken, User

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.environ.get("TOKEN_ENCRYPTION_KEY")
        if not key:
            raise RuntimeError("TOKEN_ENCRYPTION_KEY env var not set")
        _fernet = Fernet(key.encode())
    return _fernet


def _enc(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def _dec(value: str) -> str:
    return _get_fernet().decrypt(value.encode()).decode()


def save_token(db: Session, user: User, creds) -> OAuthToken:
    """Upsert an OAuthToken row for this user, encrypting sensitive fields."""
    expires_at = None
    if creds.expiry:
        expires_at = creds.expiry if isinstance(creds.expiry, datetime.datetime) else None

    token_row = db.query(OAuthToken).filter(OAuthToken.user_id == user.id).first()
    if token_row is None:
        token_row = OAuthToken(user_id=user.id)
        db.add(token_row)

    token_row.access_token_enc = _enc(creds.token or "")
    token_row.refresh_token_enc = _enc(creds.refresh_token or "") if creds.refresh_token else ""
    token_row.token_uri = creds.token_uri or "https://oauth2.googleapis.com/token"
    token_row.client_id = creds.client_id or ""
    token_row.client_secret_enc = _enc(creds.client_secret or "") if creds.client_secret else ""
    token_row.scopes = " ".join(sorted(creds.scopes or []))
    token_row.expires_at = expires_at

    db.commit()
    db.refresh(token_row)
    return token_row


def get_credentials(db: Session, user_id: int):
    """Return a google.oauth2.credentials.Credentials object for this user."""
    from google.oauth2.credentials import Credentials

    token_row = db.query(OAuthToken).filter(OAuthToken.user_id == user_id).first()
    if token_row is None:
        raise ValueError(f"No token found for user_id={user_id}")

    return Credentials(
        token=_dec(token_row.access_token_enc),
        refresh_token=_dec(token_row.refresh_token_enc) if token_row.refresh_token_enc else None,
        token_uri=token_row.token_uri,
        client_id=token_row.client_id,
        client_secret=_dec(token_row.client_secret_enc) if token_row.client_secret_enc else None,
        scopes=token_row.scopes.split(),
    )
