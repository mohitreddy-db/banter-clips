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

    # Stripe (BR-15 Creator plan). When unset, /billing/upgrade acts as the
    # dev mock. STRIPE_PRICE_CREATOR is the recurring $9.99/mo price id.
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PRICE_CREATOR: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Meta / Instagram Business Login (BR-13 real publishing). When unset,
    # /socials/connect falls back to the mock connector.
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    # Must exactly match an OAuth redirect URI registered in the Meta app.
    IG_REDIRECT_URI: str = ""
    # Where the OAuth callback sends the browser afterwards.
    FRONTEND_URL: str = "http://localhost:5173"

    MEDIA_DIR: Path = BASE_DIR / "data" / "media"

    # Where generated artifacts live. "local" writes under MEDIA_DIR and
    # serves them from /media (dev, and fine for a single box). "supabase"
    # uploads to Supabase Storage — no new vendor, since auth already uses it.
    STORAGE_BACKEND: str = "local"
    STORAGE_BUCKET: str = "clips"
    # Service-role key: server-side only, never sent to a browser. Needed to
    # upload and delete; the anon key cannot (row-level security refuses it).
    # Named as Supabase names it in the dashboard, so there is no translation
    # step between copying it and pasting it.
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    # Working files (per-scene clips, rejected keyframes) are deleted after
    # this many days. The deliverable and its poster are kept for the clip's
    # lifetime. Measured: ~14 MB worth keeping per 15s clip, ~38 MB scratch.
    SCRATCH_RETENTION_DAYS: int = 7

    # ── Video generation ────────────────────────────────────────────────
    # "dummy" keeps the pre-rendered demo clip (instant, free). "mock" walks
    # the real step sequence at real pacing without generating anything —
    # for reviewing the flow. "real" runs the pipeline in app/video and
    # spends money. Flip back to "dummy" to roll back instantly.
    PIPELINE_MODE: str = "dummy"

    # How generation is dispatched. "thread" runs it inside the API process —
    # simple, and fine for development. "postgres" writes a job row that a
    # separate worker (`python -m app.worker`) picks up, so a deploy cannot
    # lose an in-flight render. Production should use postgres.
    QUEUE_MODE: str = "thread"
    # How much faster than real time the mock runs. 1.0 = true timings
    # (~4.5 min for a 15s clip); 12 = a review pass in about 20 seconds.
    MOCK_SPEED: float = 12.0

    # Planning and keyframe review (text in / text out). Without a key the
    # planner falls back to a deterministic template and review is skipped —
    # the job still produces a video. The plan model is where script quality
    # comes from, so it gets a capable model; the reviewer only fills a
    # yes/no rubric on an image, so it stays on a cheap vision model.
    OPENAI_API_KEY: str = ""
    OPENAI_PLAN_MODEL: str = "gpt-4.1"
    OPENAI_REVIEW_MODEL: str = "gpt-4o-mini"

    # Optional web research for off-catalog cast members ("off" | "openai").
    # With "openai", an unknown name triggers one web-search call to write a
    # real look description before any image spend. Never fatal.
    WEB_RESEARCH: str = "off"
    OPENAI_RESEARCH_MODEL: str = "gpt-4.1-mini"

    # Images and video (OpenRouter). Both default to offline stubs so the
    # pipeline runs end to end with no key and no spend.
    OPENROUTER_API_KEY: str = ""
    IMAGE_PROVIDER: str = "stub"        # "stub" | "openrouter"
    IMAGE_MODEL: str = "x-ai/grok-imagine-image-quality"
    VIDEO_PROVIDER: str = "stub"        # "stub" | "openrouter"
    VIDEO_MODEL: str = "x-ai/grok-imagine-video-1.5"
    VIDEO_RESOLUTION: str = "720p"      # 480p | 720p | 1080p

    # Hard ceiling per job. Cost scales with duration, so a runaway plan is
    # expensive; the pipeline degrades to stills rather than exceeding this.
    MAX_JOB_COST_USD: float = 8.0

    # Plan matrix (BR-15). Only successful videos count (BR-09).
    PLAN_LIMITS: dict = {"free": 5, "creator": 30}
    CREATOR_PRICE: str = "$9.99/mo"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
