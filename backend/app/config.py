from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    DATABASE_URL: str = "postgresql+psycopg://banter:banter_dev@localhost:5433/banterclips"
    JWT_SECRET: str = "dev-only-secret"
    CORS_ORIGINS: str = "http://localhost:5173"
    DEV_MODE: bool = True
    STAGE_SECONDS: float = 1.4
    API_BASE_URL: str = "http://localhost:8000"

    # Supabase Auth (production sign-in). The backend verifies access tokens
    # against {SUPABASE_URL}/auth/v1/user and issues its own session JWT.
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""

    MEDIA_DIR: Path = BASE_DIR / "data" / "media"

    # Plan matrix (BR-15). Only successful videos count (BR-09).
    PLAN_LIMITS: dict = {"free": 5, "creator": 30}
    CREATOR_PRICE: str = "$9.99/mo"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
