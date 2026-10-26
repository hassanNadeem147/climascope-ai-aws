from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.database.base import Base
from app.logging.logger import logger


# Load application settings once.
settings = get_settings()

# Create the asynchronous database engine.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def initialize_database() -> None:
    """Create missing application tables and verify the database connection."""
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(text("SELECT 1"))
        logger.info("Database schema initialized and connection verified.")
    except Exception:
        logger.exception("Failed to initialize the PostgreSQL database.")
        raise


async def verify_db_connection() -> None:
    """Check whether the PostgreSQL database is reachable."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        logger.info("Database connection verified successfully.")
    except Exception:
        logger.exception("Failed to connect to PostgreSQL.")
        raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for one request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            logger.exception("Database session rolled back.")
            raise


async def close_db_connection() -> None:
    """Close database connections during application shutdown."""
    await engine.dispose()
    logger.info("Database connections closed.")