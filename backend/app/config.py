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
    # dev mock. STRIPE_PRICE_CREATOR is the recurring monthly price id ($19 since 2026-08-26; earlier subs grandfathered at $9.99).
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

    # TikTok Login Kit + Content Posting API (BR-13). When unset,
    # /socials/connect falls back to the mock connector, same as Instagram.
    TIKTOK_CLIENT_KEY: str = ""
    TIKTOK_CLIENT_SECRET: str = ""
    # Must exactly match a redirect URI registered in the TikTok app
    # (https only — use a tunnel for local dev, like IG_REDIRECT_URI).
    TIKTOK_REDIRECT_URI: str = ""
    # Scopes requested at authorize time. Every scope listed here must be
    # enabled on the TikTok app or the consent screen errors out, so trim
    # via env rather than code if the portal config differs.
    #
    # Exactly what we use, and no more: TikTok's audit treats a scope the
    # integration cannot be seen exercising as a reason to reject. video.publish
    # covers Direct Post (/post/publish/video/init/), which is our only publish
    # path; video.upload is the draft-to-inbox scope, and we never post drafts.
    # Add it back the day we offer "send to your TikTok drafts".
    TIKTOK_SCOPES: str = "user.info.basic,video.publish"
    # Optional HTTP forward proxy for ALL TikTok API traffic (authorize URL
    # excluded — that's the user's browser). TikTok is ISP-blocked in India
    # and geo-sensitive about request origin, so TikTok calls can ride a US
    # box (tinyproxy on the NYC droplet) regardless of where this backend
    # runs: http://user:pass@146.190.213.29:8899. Empty = direct.
    TIKTOK_PROXY_URL: str = ""
    # Whether our TikTok client has yet to pass the content audit. Unaudited
    # (and every sandbox) client may only post privately, and only to a
    # private account — TikTok enforces that itself, rejecting anything else.
    #
    # This flag does NOT override the creator's choice: the composer always
    # sends the audience they picked, because an app that silently substitutes
    # one is what TikTok's audit is looking for. All it does is warn them in
    # the dialog about what TikTok will accept today.
    #
    # Set to false once the audit clears — and remember the audit attaches to
    # a specific client key, so a sandbox key (sb...) stays restricted no
    # matter what this says.
    TIKTOK_UNAUDITED: bool = True

    # YouTube Data API OAuth + videos.insert. Unverified API projects may have
    # uploads forced private by Google even when public is requested.
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REDIRECT_URI: str = ""
    YOUTUBE_PRIVACY_STATUS: str = "public"

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
    # "real" runs the pipeline in app/video — with the default stub
    # providers this is still free and offline (placeholder stills, Ken
    # Burns); it only spends money once IMAGE/VIDEO_PROVIDER=openrouter.
    # "mock" walks the real step sequence at real pacing without generating;
    # "dummy" attaches the pre-rendered demo clip instantly. The mock flow
    # also always runs for a take containing [mock], whatever this is set to
    # — that marker is the one intended way to demo without generating.
    PIPELINE_MODE: str = "real"

    # How generation is dispatched. "thread" runs it inside the API process —
    # simple, and fine for development. "postgres" writes a job row that a
    # separate worker (`python -m app.worker`) picks up, so a deploy cannot
    # lose an in-flight render. Production should use postgres.
    QUEUE_MODE: str = "thread"
    # How much faster than real time the mock runs. 1.0 = true timings
    # (~4.5 min for a 15s clip); 12 = a review pass in about 20 seconds.
    MOCK_SPEED: float = 12.0
    # The video a simulated run delivers. It is uploaded per clip through the
    # normal storage path and served from its own key, so a demo exercises
    # everything except generation — upload, public URL, download, deletion.
    # A real previously-generated clip, so demos look like the product.
    SAMPLE_CLIP_PATH: Path = BASE_DIR / "data" / "media" / "sample.mp4"

    # Planning and keyframe review (text in / text out). Without a key the
    # planner falls back to a deterministic template and review is skipped —
    # the job still produces a video. The plan model is where script quality
    # comes from, so it gets a capable model; the reviewer only fills a
    # yes/no rubric on an image, so it stays on a cheap vision model.
    OPENAI_API_KEY: str = ""
    OPENAI_PLAN_MODEL: str = "gpt-4.1"
    OPENAI_REVIEW_MODEL: str = "gpt-4o-mini"

    # Who writes the video prompt. "openai" runs a shot-writer pass that
    # describes the cinematography in prose — one call per job, a fraction of
    # a cent — which reads better to a video model than fields joined by
    # labels. "off" uses the deterministic template. The guardrails (photoreal
    # anchor, negatives, no-subtitles) are appended either way.
    SHOT_WRITER: str = "openai"

    # Optional web research for off-catalog cast members ("off" | "openai").
    # With "openai", an unknown name triggers one web-search call to write a
    # real look description before any image spend. Never fatal.
    # "openai" keeps the OpenAI web_search fallback available; "off" disables
    # every research feature. Firecrawl (below) is used first when its key is set.
    WEB_RESEARCH: str = "openai"
    # Firecrawl web search — trending feed, Storyline Pack, cast research and
    # the catalog verifier all search through it (app/video/websearch.py).
    FIRECRAWL_API_KEY: str = ""
    FIRECRAWL_URL: str = "https://api.firecrawl.dev"
    OPENAI_RESEARCH_MODEL: str = "gpt-4.1-mini"

    # Images and video (OpenRouter). Both default to offline stubs so the
    # pipeline runs end to end with no key and no spend.
    OPENROUTER_API_KEY: str = ""
    IMAGE_PROVIDER: str = "stub"        # "stub" | "openrouter"
    IMAGE_MODEL: str = "x-ai/grok-imagine-image-quality"
    # Keyframes for scenes casting the user's reference photo. Grok ignores
    # attached faces (drew a different person, verified 2026-09-03); Gemini
    # reproduces them. Empty string disables the identity route entirely.
    IMAGE_IDENTITY_MODEL: str = "google/gemini-2.5-flash-image"
    VIDEO_PROVIDER: str = "stub"        # "stub" | "openrouter"
    VIDEO_MODEL: str = "x-ai/grok-imagine-video-1.5"
    # OpenRouter model per output tier. JSON in env; VIDEO_MODEL remains the
    # fallback and lets any other OpenRouter video generator work unchanged.
    # Both tiers stay on Grok: Seedance rejects any input frame containing a
    # photoreal person (InputImageSensitiveContentDetected, 2026-09-01), and
    # every BanterClips scene stars one — its cheap rates are unreachable for
    # this product. Route back only if that filter ever changes.
    VIDEO_MODEL_ROUTES: dict[str, str] = {
        "720p": "x-ai/grok-imagine-video-1.5",
        "1080p": "x-ai/grok-imagine-video-1.5",
    }
    VIDEO_RESOLUTION: str = "720p"      # 480p | 720p | 1080p

    # Script approval: generation pauses after the script is written
    # (status "script_ready") until the user approves it — no video money
    # is spent on an unapproved script. "off" generates straight through.
    SCRIPT_APPROVAL: str = "on"

    # Storyline Packs: one cached web-search call per topic per day feeds the
    # planner real current context (squad, storylines, kit, venues, personas).
    STORYLINE_CONTEXT: str = "on"

    # Comma-separated emails with access to the admin panel (/admin/*).
    ADMIN_EMAILS: str = ""

    # When a job casts a real person the catalog doesn't know (and web
    # research confirms who they are), generate their two reference stills
    # on the spot (~$0.10, charged to the job) so this character renders
    # consistently in this job and every future one. "off" skips the stills;
    # the character entry is still saved to the overlay catalog.
    CATALOG_AUTOGEN_REFS: str = "on"

    # Text burned across the top of every frame. Empty means none.
    # Applies to every plan. Note that Instagram's own policy expects
    # realistic AI-generated content to be labelled, and these videos carry
    # real athletes' likenesses — see the note in VIDEO-GENERATION-PLAN.md.
    VIDEO_DISCLOSURE: str = ""

    # Hard ceiling per job. Cost scales with duration AND resolution, so a
    # runaway plan is expensive; a job that would exceed this stops rather
    # than overspending. Sized for the dearest legitimate job — 30s at 1080p
    # (~2x the measured $0.147/s at 720p) — so the cap only catches runaways,
    # never a job a Creator was allowed to ask for.
    MAX_JOB_COST_USD: float = 14.0
    # Render preflight floor. 0 by request: run the balance all the way down —
    # a scene that 402s mid-render pauses with its checkpoint and resumes free,
    # so the floor only guards the pointless case (balance already ≤ 0, where
    # every submit is doomed). Raise via env if pre-auth flakiness ever needs
    # headroom again (2026-08: refusals seen with as much as $9.65 left).
    PROVIDER_MIN_BALANCE_USD: float = 0.0
    # Ceiling across ALL jobs in a rolling 24 hours. The per-job limit stops
    # one runaway clip; this stops a normal day from emptying the account,
    # which at ~$2.40 a clip takes very few users. Past it, generation is
    # refused with an honest message instead of failing halfway through and
    # leaving half-paid-for clips. 0 disables the check.
    MAX_DAILY_SPEND_USD: float = 25.0

    # Plan matrix (BR-15). Only successful videos count (BR-09).
    PLAN_LIMITS: dict = {"free": 5, "creator": 30}
    CREATOR_PRICE: str = "$19/mo"

    @property
    def admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
