from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL
class Settings(BaseSettings):
    """Application configuration settings."""
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
    # AWS settings
    AWS_ACCESS_KEY_ID: SecretStr
    AWS_SECRET_ACCESS_KEY: SecretStr
    AWS_REGION: str
    BUCKET_NAME: str
    # LLM settings
    GROQ_API_KEY: SecretStr
    GROQ_MODEL: str
    # Qdrant settings
    QDRANT_API_KEY: SecretStr
    QDRANT_URL: SecretStr
    # PostgreSQL settings
    DATABASE_NAME: str
    DATABASE_USERNAME: str
    DATABASE_HOST: str
    DATABASE_PORT: int = 5432
    DATABASE_PASSWORD: SecretStr
    DATABASE_SSLMODE: str = "require"
    JWT_SECRET_KEY: SecretStr | None = None
    JWT_ACCESS_TOKEN_EXPIRE_SECONDS: int = Field(default=1800, gt=0, le=86400)

    # Build the database URL
    @property
    def DATABASE_URL(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.DATABASE_USERNAME,
            password=self.DATABASE_PASSWORD.get_secret_value(),
            host=self.DATABASE_HOST,
            port=self.DATABASE_PORT,
            database=self.DATABASE_NAME,
            query={"ssl": self.DATABASE_SSLMODE},
        )

    @property
    def CHECKPOINT_DATABASE_URL(self) -> str:
        """Return a libpq-compatible URL for LangGraph's async PostgreSQL saver."""
        return self.DATABASE_URL.set(
            drivername="postgresql",
            query={"sslmode": self.DATABASE_SSLMODE},
        ).render_as_string(hide_password=False)


@lru_cache()
def get_settings() -> Settings:
    """Load settings once and reuse them."""
    return Settings()