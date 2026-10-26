from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import InvalidTokenError, decode_access_token
from app.database.session import get_db
from app.models.user import User


_bearer_scheme = HTTPBearer(auto_error=False)


def _get_jwt_secret() -> str:
    secret = get_settings().JWT_SECRET_KEY
    if secret is None or len(secret.get_secret_value().encode("utf-8")) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is unavailable until JWT_SECRET_KEY is configured.",
        )
    return secret.get_secret_value()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        claims = decode_access_token(credentials.credentials, _get_jwt_secret())
        user_id = UUID(claims["sub"])
    except (InvalidTokenError, ValueError, KeyError):
        raise unauthorized from None

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user
