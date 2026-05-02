"""Supabase JWT verification + role checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

log = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class AuthUser:
    """Authenticated user resolved from a Supabase JWT."""
    user_id: str           # auth.users.id (UUID string)
    email: str | None
    role: str              # 'authenticated' typically
    raw_claims: dict


def _decode_token(token: str) -> dict:
    """Verify the JWT signature with Supabase's HS256 secret and return claims."""
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        log.warning("Invalid JWT: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> AuthUser:
    """FastAPI dependency: resolves the current authenticated user."""
    claims = _decode_token(credentials.credentials)
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )
    return AuthUser(
        user_id=user_id,
        email=claims.get("email"),
        role=claims.get("role", "authenticated"),
        raw_claims=claims,
    )


CurrentUser = Annotated[AuthUser, Depends(current_user)]
