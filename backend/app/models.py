import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

SPORTS = ("NBA", "NFL", "Soccer", "MLB")
TONES = ("Funny", "Savage", "Hype", "Bold")
PLATFORMS = ("instagram", "tiktok", "youtube", "x", "linkedin")

# Honest generation stages (BR-07), in order. Index into this list = stage_index.
GENERATION_STAGES = (
    "planning_story",
    "creating_voice",
    "designing_characters",
    "generating_scenes",
    "animating_scenes",
    "assembling_video",
    "validating",
)
# "script_ready" = the script is written and awaiting the user's approval
# before any generation money is spent (script approval flow).
CLIP_STATUSES = ("queued", *GENERATION_STAGES, "script_ready", "ready", "failed")


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # Supabase Auth user id (auth.users.id) once the account signs in via Supabase.
    supabase_uid: Mapped[str | None] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[str] = mapped_column(Text, nullable=False, server_default="free")
    plan_renews_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    stripe_customer_id: Mapped[str | None] = mapped_column(Text, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Blocklist. A blocked account is never told it is blocked: sign-in
    # returns the same generic 401 as a bad token, and existing sessions die
    # the same way — from the outside it looks like a login that won't stick.
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # One wallet (PRICING.md rule 1) — cached balance; every change also
    # writes a CreditEntry, which is the source of truth for audits.
    credits: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    @property
    def is_admin(self) -> bool:
        """Admin = allow-listed email. The env list (ADMIN_EMAILS) is the
        bootstrap and can never be removed from the console; the admin page
        manages additions on top (services/admin_allowlist)."""
        from .services import admin_allowlist

        return admin_allowlist.is_admin_email(self.email)

    preferences: Mapped["UserPreferences | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (CheckConstraint("plan IN ('free','creator')", name="users_plan_check"),)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    sports: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    teams: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    players: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    role: Mapped[str | None] = mapped_column(Text)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="preferences")


class LoginToken(Base):
    __tablename__ = "login_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


JOB_STATUSES = ("queued", "running", "done", "failed")


class Job(Base):
    """Durable work queue.

    Generation used to run on a daemon thread inside the API process, so a
    deploy or a crash mid-job lost the work silently: the clip stayed pinned
    in a generating status and the user's minutes were gone. A row per job
    survives both, and lets a separate worker process do the heavy lifting so
    restarting the API never interrupts a render.

    Postgres rather than Redis or SQS: the database is already here, already
    backed up, and `SELECT ... FOR UPDATE SKIP LOCKED` is exactly the
    primitive a queue needs. Adding a broker would be a second thing to
    operate for no capability we lack.
    """

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    # The clip this job is for. Unique among live jobs, so a double-click or a
    # retried request cannot render the same clip twice.
    clip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")
    # Not before this time — used for retry backoff.
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Which worker holds it, and when it last said it was alive. A lock that
    # goes stale (worker killed) is reclaimed rather than stranding the job.
    locked_by: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"status IN {JOB_STATUSES!r}", name="jobs_status_check"),
        # The claim query orders by these; without it every poll is a seq scan.
        Index("jobs_claimable", "status", "run_after"),
    )


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    take: Mapped[str] = mapped_column(Text, nullable=False)
    sport: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    stage_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    # Requested length in seconds (10/15/30); >15 is Creator-only.
    duration_target: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15")
    # Requested output resolution ("720p"/"1080p"); 1080p is Creator-only.
    resolution: Mapped[str] = mapped_column(Text, nullable=False, server_default="720p")
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(4, 1))
    video_url: Mapped[str | None] = mapped_column(Text)
    thumb_gradient: Mapped[str | None] = mapped_column(Text)
    watermarked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # What the pipeline is doing right now, in the user's language ("Designing
    # scene 1 of 2"). On the row rather than in process memory because the API
    # runs multiple workers: a poll can land on a worker that is not running
    # the job, and in-memory state would read as empty half the time.
    current_step: Mapped[str | None] = mapped_column(Text)

    # Storage keys for the artifacts we keep. video_url is derived from
    # video_key and stays for the client and for Instagram's fetcher.
    video_key: Mapped[str | None] = mapped_column(Text)
    poster_key: Mapped[str | None] = mapped_column(Text)

    # What it cost us, and how it was made: the brief, the plan, per-scene
    # review verdicts and model versions. Small, and the only way to answer
    # "why did this clip come out like that" after the scratch files expire.
    cost_usd: Mapped[float | None] = mapped_column(Numeric(7, 3))
    provenance: Mapped[dict | None] = mapped_column(JSONB)

    # The credit receipt (PRICING.md rule 4): what this video charged. Set on
    # create (the reservation), zeroed by a refund — so >0 on a failed clip
    # means "refund pending", and the ledger explains every change.
    credits_charged: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Simulated clips ([mock] in the take, or dummy mode) never reach a real
    # audience: publishing is refused and no allowance is consumed.
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # The SCRIPT — the full detailed plan (shots, cast, every dialogue line)
    # written before any pixel is generated. Kept on the row permanently so
    # every video's script stays viewable ("Show script"). With script
    # approval on, generation pauses at status "script_ready" until the user
    # approves; rejected drafts accumulate in script_history.
    script: Mapped[dict | None] = mapped_column(JSONB)
    script_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    script_history: Mapped[list | None] = mapped_column(JSONB)

    publishes: Mapped[list["Publish"]] = relationship(
        back_populates="clip", cascade="all, delete-orphan", order_by="Publish.created_at.desc()"
    )

    __table_args__ = (
        CheckConstraint("char_length(take) BETWEEN 10 AND 280", name="clips_take_len"),
        CheckConstraint(f"sport IN {SPORTS!r}", name="clips_sport_check"),
        CheckConstraint(f"tone IN {TONES!r}", name="clips_tone_check"),
        Index("clips_owner_month", "user_id", "status", "completed_at"),
    )


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    handle: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="connected")
    access_token: Mapped[str | None] = mapped_column(Text)
    # TikTok only: its access tokens last 24h and roll via this year-long
    # refresh token. Instagram's long-lived token refreshes itself, so NULL.
    refresh_token: Mapped[str | None] = mapped_column(Text)
    # The platform-side user id (IG professional account id / TikTok open_id).
    platform_user_id: Mapped[str | None] = mapped_column(Text)
    # When the long-lived token expires; refreshed automatically near expiry.
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("user_id", "platform", name="social_one_per_platform"),)


class Publish(Base):
    __tablename__ = "publishes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    clip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False
    )
    social_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False
    )
    caption: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    clip: Mapped[Clip] = relationship(back_populates="publishes")
    account: Mapped[SocialAccount] = relationship()

    __table_args__ = (Index("publishes_clip", "clip_id", "created_at"),)


class StripeEvent(Base):
    """Audit log + idempotency marker for processed Stripe webhook events.
    Stripe itself is the billing ledger; this table records which deliveries
    we acted on (at-least-once delivery means retries and duplicates)."""

    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # evt_...
    type: Mapped[str] = mapped_column(Text, nullable=False)
    event_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    props: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("events_name_time", "name", "created_at"),)


class CatalogCharacter(Base):
    """Persistent character catalog — the DB half of the two-layer catalog.

    The curated JSON in app/video/catalog/ ships with the code; rows here are
    written at runtime (auto-research discoveries) and by the admin catalog
    page, and OVERRIDE the JSON entry with the same id. Reference stills for
    these rows live in Supabase Storage (keys in reference_images), so the
    whole dynamic layer survives droplet rebuilds and works across processes.
    """

    __tablename__ = "catalog_characters"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # slug, e.g. "ronaldinho"
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sport: Mapped[str] = mapped_column(Text, nullable=False, server_default="NBA")
    look: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    default_wardrobe: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    voice_style: Mapped[str] = mapped_column(Text, nullable=False, server_default="neutral, conversational")
    aliases: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    teams: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # Supabase Storage keys ("catalog/references/x.jpg") or repo-relative
    # paths ("references/x.jpg") for entries that mirror a curated character.
    reference_images: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # "auto-research" (pipeline discovered) | "admin" (created/edited by hand)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="auto-research")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CatalogStill(Base):
    """Every reference still ever generated for a character — the history.

    A character's ACTIVE references stay on catalog_characters.reference_images
    (a list of storage keys / repo paths); a still row is "active" when its
    key is in that list. Keeping every generation lets an admin approve the
    good batch, roll back to an older look, or mix stills across batches.
    """

    __tablename__ = "catalog_stills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    character_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="full")  # face | full
    # Where the bytes live: a Supabase Storage key, and/or a repo-relative
    # path ("references/x.jpg") when the upload failed or the file is curated.
    storage_key: Mapped[str | None] = mapped_column(Text)
    local_path: Mapped[str | None] = mapped_column(Text)
    # The admin's generation direction ("2005 Barcelona era, long curly hair").
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="admin")  # admin | auto
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("catalog_stills_char", "character_id", "created_at"),)


class AdminAction(Base):
    """Append-only audit log of every mutating admin-console action.

    ADMIN.md §5.1: who, action, target, reason, timestamp. Rows are written
    by the admin router only and never updated or deleted from the app.
    """

    __tablename__ = "admin_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    admin_email: Mapped[str] = mapped_column(Text, nullable=False)
    # Short verb slug, e.g. "block_user", "set_daily_cap", "delete_clip".
    action: Mapped[str] = mapped_column(Text, nullable=False)
    # Human-readable object, e.g. "user someone@x.com", "clip 8f2a…".
    target: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    reason: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("admin_actions_time", "created_at"),)


class RuntimeSetting(Base):
    """Small key/value store for operator-editable runtime settings.

    Replaces SSH-editing .env for the spend caps and holds the generation
    kill switch plus the worker heartbeat. Values are stored as text and
    parsed by services.runtime_settings; env vars remain the fallback so a
    fresh database behaves exactly as before.
    """

    __tablename__ = "runtime_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StorylinePack(Base):
    """Cached real-world context (see app/video/context.py) — one pack per
    topic per day, so repeat takes about the same team cost ~nothing."""

    __tablename__ = "storyline_packs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    topic_key: Mapped[str] = mapped_column(Text, nullable=False)
    day: Mapped[datetime] = mapped_column(Date, nullable=False)
    pack: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("topic_key", "day", name="storyline_topic_day"),)


CREDIT_KINDS = (
    "grant_signup",    # one-time 60 on account creation
    "grant_monthly",   # Creator's monthly credits
    "grant_admin",     # manual grant/deduction from the admin console
    "topup",           # purchased pack (Stripe one-time payment)
    "video_charge",    # reservation when a generation starts
    "video_refund",    # release when it fails or is abandoned
    "enhance_charge",  # per press of "Enhance take"
)


class CreditEntry(Base):
    """The credit ledger — one row per wallet movement, append-only.

    `users.credits` is a cached sum for cheap reads; this table is the truth.
    `balance_after` makes any point-in-time balance reconstructible without
    summing the whole history."""

    __tablename__ = "credit_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    clip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clips.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(f"kind IN {CREDIT_KINDS!r}", name="credit_entries_kind_check"),
        Index("credit_entries_user", "user_id", "created_at"),
    )


class TrendingPack(Base):
    """Cached create-page trending feed (see app/video/trending.py) — one
    row per sport, shared by all users, refreshed when older than the TTL."""

    __tablename__ = "trending_packs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    sport: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    pack: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
