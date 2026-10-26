from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.core.config import get_settings
from app.database.session import (
    close_db_connection,
    initialize_database,
    verify_db_connection,
)
from app.graph.workflow import create_workflow
from app.logging.logger import logger


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    try:
        await initialize_database()
        async with AsyncPostgresSaver.from_conn_string(
            settings.CHECKPOINT_DATABASE_URL
        ) as checkpointer:
            await checkpointer.setup()
            application.state.workflow = create_workflow(checkpointer=checkpointer)
            logger.info("ClimaScope API startup completed.")
            yield
    except Exception:
        logger.exception("ClimaScope API startup or shutdown failed.")
        raise
    finally:
        await close_db_connection()
        logger.info("ClimaScope API shutdown completed.")


app = FastAPI(
    title="ClimaScope AI API",
    version="1.0.0",
    description="Climate document question answering and user account API.",
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api/v1")

_frontend_directory = Path(__file__).resolve().parent.parent / "frontend"


@app.middleware("http")
async def add_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'none'; object-src 'none'; "
        "form-action 'none'; frame-ancestors 'none'; script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "media-src https://d8j0ntlcm91z4.cloudfront.net; "
        "img-src 'self' data:; connect-src 'self'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    try:
        await verify_db_connection()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is unavailable.",
        ) from exc
    return {"status": "ok"}


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    logger.opt(exception=exc).error(
        "Unhandled database error on {} {}.",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is temporarily unavailable."},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.opt(exception=exc).error(
        "Unhandled API error on {} {}.",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )


app.mount(
    "/",
    StaticFiles(directory=_frontend_directory, html=True),
    name="frontend",
)