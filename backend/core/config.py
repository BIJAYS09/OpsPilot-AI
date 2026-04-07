"""
Central config — reads from environment / .env file.
All other modules import from here, never from os.getenv directly.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Energy Co-pilot API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # ── Auth ─────────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── TimescaleDB ───────────────────────────────────────────────────────────
    TIMESCALE_HOST: str = "localhost"
    TIMESCALE_PORT: int = 5432
    TIMESCALE_DB: str = "energy_copilot"
    TIMESCALE_USER: str = "postgres"
    TIMESCALE_PASSWORD: str = "yourpassword"
    TIMESCALE_POOL_MIN: int = 2
    TIMESCALE_POOL_MAX: int = 15

    # ── Qdrant ────────────────────────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str = ""

    # ── Embedding ─────────────────────────────────────────────────────────────
    EMBEDDING_BACKEND: str = "sentence-transformers"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    OPENAI_API_KEY: str = ""

    # ── Anthropic ─────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    # ── WebSocket ─────────────────────────────────────────────────────────────
    WS_HEARTBEAT_SECONDS: int = 30
    WS_SENSOR_PUSH_SECONDS: int = 5      # how often to push live sensor updates

    # ── Data ─────────────────────────────────────────────────────────────────
    DATA_DIR: str = "./data"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def timescale_dsn(self) -> str:
        return (
            f"postgresql://{self.TIMESCALE_USER}:{self.TIMESCALE_PASSWORD}"
            f"@{self.TIMESCALE_HOST}:{self.TIMESCALE_PORT}/{self.TIMESCALE_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
