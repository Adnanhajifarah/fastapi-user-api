import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# SECRET_KEY signs every token. Anyone holding it can mint a valid token for any
# user, so it must stay secret. The development default below exists only so the
# app runs locally with zero setup - but it is committed to a public repository,
# which means it is not secret at all.
#
# Hence the guard: when APP_ENV says production, refuse to start rather than
# quietly signing real tokens with a key anyone can read. A crash on deploy is a
# bad afternoon; shipping this key is forged logins for every account.
APP_ENV = os.environ.get("APP_ENV", "development")
_DEVELOPMENT_SECRET = "dev-only-change-me"
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", _DEVELOPMENT_SECRET)

if APP_ENV == "production" and SECRET_KEY == _DEVELOPMENT_SECRET:
    raise RuntimeError(
        "JWT_SECRET_KEY must be set when APP_ENV=production. Refusing to start: "
        "the development signing key is public, so anyone could forge a token "
        "for any user."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "30"))

# Tells FastAPI to look for an "Authorization: Bearer <token>" header and
# powers the Authorize button in /docs.
bearer_scheme = HTTPBearer()


def create_access_token(subject: str, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    """Create a signed JWT whose `sub` claim identifies the user (their email)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Verify a token's signature and expiry, returning its payload or raising 401."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """FastAPI dependency: extract the bearer token, verify it, return the email (sub).

    Any route that adds `Depends(get_current_user)` becomes protected: a missing
    or invalid token is rejected before the route body ever runs.
    """
    payload = decode_access_token(credentials.credentials)
    email = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return email
