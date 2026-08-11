import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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
CLIP_STATUSES = ("queued", *GENERATION_STAGES, "ready", "failed")


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
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(4, 1))
    video_url: Mapped[str | None] = mapped_column(Text)
    thumb_gradient: Mapped[str | None] = mapped_column(Text)
    watermarked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
    # The platform-side user id (Instagram professional account id).
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
