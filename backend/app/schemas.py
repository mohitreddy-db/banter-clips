import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Sport = Literal["NBA", "NFL", "Soccer", "MLB"]
Tone = Literal["Funny", "Savage", "Hype"]
Platform = Literal["instagram", "tiktok", "youtube", "x", "linkedin"]
Role = Literal["Sports Fan", "Creator", "Podcaster", "Media Company", "Fantasy Creator"]


# ---------- auth ----------
class MagicLinkRequest(BaseModel):
    email: EmailStr
    display_name: str | None = None


class MagicLinkResponse(BaseModel):
    sent: bool = True
    # DEV_MODE only — in production the token is emailed, never returned.
    dev_token: str | None = None


class VerifyRequest(BaseModel):
    token: str


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


# ---------- users ----------
class PreferencesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sports: list[str] = []
    teams: list[str] = []
    players: list[str] = []
    role: str | None = None
    onboarding_completed: bool = False


class PreferencesUpdate(BaseModel):
    sports: list[str] | None = None
    teams: list[str] | None = None
    players: list[str] | None = None
    role: Role | None = None
    onboarding_completed: bool | None = None


class UsageOut(BaseModel):
    plan: Literal["free", "creator"]
    used: int
    limit: int
    left: int
    can_download: bool
    watermarked: bool


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    plan: str
    cancel_at_period_end: bool
    created_at: datetime
    preferences: PreferencesOut | None = None


# ---------- clips ----------
class ClipCreate(BaseModel):
    take: str = Field(min_length=10, max_length=280)
    sport: Sport
    tone: Tone


class PublishOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clip_id: uuid.UUID
    social_account_id: uuid.UUID
    caption: str
    status: str
    error: str | None
    external_url: str | None
    created_at: datetime
    published_at: datetime | None
    platform: str | None = None
    handle: str | None = None


class ClipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    take: str
    sport: str
    tone: str
    status: str
    stage_index: int
    error: str | None
    duration_seconds: float | None
    video_url: str | None
    thumb_gradient: str | None
    watermarked: bool
    created_at: datetime
    completed_at: datetime | None
    publishes: list[PublishOut] = []


# ---------- socials ----------
class SocialConnectRequest(BaseModel):
    platform: Platform


class SocialAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: str
    handle: str
    status: str
    connected_at: datetime


# ---------- publishing ----------
class PublishCreate(BaseModel):
    social_account_id: uuid.UUID
    caption: str = Field(default="", max_length=2200)


# ---------- billing ----------
class PlanChangeResponse(BaseModel):
    plan: str
    cancel_at_period_end: bool
    message: str


# ---------- analytics ----------
class EventIn(BaseModel):
    name: str = Field(max_length=64)
    props: dict = {}
