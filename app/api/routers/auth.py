import asyncio
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import _get_jwt_secret
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.database.session import get_db
from app.logging.logger import logger
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserRead


router = APIRouter(prefix="/auth", tags=["authentication"])
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Create a user account; only the password hash is persisted."""
    existing_user = await db.scalar(select(User.id).where(User.email == payload.email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    password_hash = await asyncio.to_thread(hash_password, payload.password)
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=password_hash,
    )
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as exc:
        await db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            ) from exc
        logger.exception("Database constraint failed during user registration.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The account could not be created.",
        ) from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception("Database error during user registration.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is temporarily unavailable.",
        ) from exc
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Verify account credentials and issue a signed bearer token."""
    try:
        user = await db.scalar(select(User).where(User.email == payload.email))
    except SQLAlchemyError as exc:
        logger.exception("Database error during user login.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is temporarily unavailable.",
        ) from exc

    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_matches = await asyncio.to_thread(
        verify_password,
        payload.password,
        password_hash,
    )
    if user is None or not user.is_active or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS
    try:
        access_token = create_access_token(
            {"sub": str(user.id)},
            _get_jwt_secret(),
            expires_in_seconds=expires_in,
        )
    except ValueError as exc:
        logger.error("JWT configuration is invalid: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is unavailable due to invalid JWT configuration.",
        ) from exc
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserRead.model_validate(user),
    )