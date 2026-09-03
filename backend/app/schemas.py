import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import SPORTS, TONES

# Built from the model tuples, so the API, the database check constraints and
# the pipeline vocabulary can never drift apart — adding a sport is a one-line
# change in models.py.
Sport = Literal[SPORTS]  # type: ignore[valid-type]
Tone = Literal[TONES]  # type: ignore[valid-type]
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
    # Video-count limits are gone (credits are the unit); kept nullable for
    # stale clients, with `left` mapped onto the credit balance.
    limit: int | None = None
    left: int
    credits: int = 0
    # The public price list: what actions cost, so the client quotes exactly.
    prices: dict = {}
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
    # Read from the User.is_admin property (ADMIN_EMAILS allow-list); shows
    # the admin nav in the client. Endpoints enforce it server-side.
    is_admin: bool = False


# ---------- clips ----------
class ClipCreate(BaseModel):
    take: str = Field(min_length=10, max_length=500)
    # Optional, not a gate: most takes name a league, club or player, so the
    # sport is inferred from the words when nothing is ticked (video/sports.py).
    # `sports` carries a multi-select — a take can straddle two ("NBA + NFL")
    # — and the first one is the world the video is built in.
    sport: Sport | None = None
    sports: list[Sport] = Field(default_factory=list, max_length=4)
    # Optional teams/players the user wants in it, in their own words.
    subjects: list[str] = Field(default_factory=list, max_length=8)
    direction: str = Field(default="", max_length=400)
    reference_key: str | None = Field(default=None, max_length=300)
    tone: Tone
    duration: Literal[10, 15, 30] = 15
    resolution: Literal["720p", "1080p"] = "720p"


# ---------- prompt enhancement ----------
class EnhanceRequest(BaseModel):
    """Anything the user has typed so far. Every field is optional except the
    take, because the point of enhancement is to work out what is missing."""

    take: str = Field(max_length=500, default="")
    sport: Sport | None = None
    tone: Tone | None = None
    duration: int | None = None
    # question id -> chosen value, from a previous round of answers.
    answers: dict[str, str] = Field(default_factory=dict)


class EnhanceOptionOut(BaseModel):
    value: str
    label: str
    detail: str = ""


class EnhanceQuestionOut(BaseModel):
    id: str
    prompt: str
    why: str
    kind: str = "choice"
    default: str = ""
    required: bool = False
    options: list[EnhanceOptionOut] = []


class EnhanceOut(BaseModel):
    """The sharpened brief plus whatever is still worth asking."""

    take: str
    original_take: str = ""
    sport: str
    tone: str
    seconds: int
    style_id: str
    style: str
    style_label: str = ""
    cast_ids: list[str] = []
    team_ids: list[str] = []
    cast_names: list[str] = []
    team_names: list[str] = []
    unknown_names: list[str] = []
    questions: list[EnhanceQuestionOut] = []
    source: str = "fallback"




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
    # What the user picked beyond the primary sport, echoed back so the UI can
    # show what the video was actually built from.
    sports: list[str] = []
    subjects: list[str] = []
    tone: str
    status: str
    stage_index: int
    error: str | None
    duration_target: int = 15
    resolution: str = "720p"
    duration_seconds: float | None
    video_url: str | None
    thumb_gradient: str | None
    watermarked: bool
    created_at: datetime
    completed_at: datetime | None
    publishes: list[PublishOut] = []
    # What the pipeline is doing right now, in the user's language. Read from
    # the row, so it is correct whichever worker serves the poll.
    current_step: str | None = None
    is_simulated: bool = False
    # The full script (shots, cast, dialogue), recorded for every video and
    # shown by "Show script". With approval on, status "script_ready" holds
    # generation until the user approves or regenerates it.
    script: dict | None = None
    script_approved: bool = False
    # A real frame from the clip, for thumbnails. None for clips made before
    # posters were stored, so the client keeps its gradient fallback.
    poster_url: str | None = None
    # The user's uploaded reference photo/video, shown with the clip so it is
    # always clear what the generation was anchored to. None when none given.
    reference_url: str | None = None
    # The credit receipt (PRICING rule 4): what this video charged. 0 after a
    # refund and for clips that predate the credit system.
    credits_charged: int = 0
    # Scene edits: what re-rendering chosen scenes has charged so far, the
    # edit currently in flight (if any), and whether one can be requested —
    # the untouched scenes must still be on disk (7 days), so this is
    # computed only for GET /clips/{id}.
    credits_edits: int = 0
    edit_pending: dict | None = None
    editable: bool = False


class CaptionSuggestions(BaseModel):
    captions: list[str] = []


class TakeEnhanceRequest(BaseModel):
    take: str = Field(min_length=1, max_length=500)
    sport: Sport | None = None
    tone: Tone | None = None
    # How many times the user has already asked. Only widens the search, so
    # repeat clicks return genuinely different ideas rather than rephrasings.
    round: int = 0


class TakeVariation(BaseModel):
    take: str
    angle: str = ""
    why: str = ""


class TakeEnhanceResponse(BaseModel):
    original: str
    variations: list[TakeVariation] = []


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
class TikTokOptions(BaseModel):
    """What the creator chose in the TikTok composer.

    TikTok's Content Sharing Guidelines make every one of these a creator
    decision rather than an app default: the privacy level must be picked
    explicitly (no pre-selection), the three interaction permissions start
    off, and commercial content must be disclosed by the person posting.
    The API mirrors that — there is no default privacy_level here.
    """

    privacy_level: Literal[
        "PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY"
    ]
    allow_comment: bool = False
    allow_duet: bool = False
    allow_stitch: bool = False
    # Commercial content disclosure: "Your brand" → Promotional content label,
    # "Branded content" → Paid partnership label.
    brand_organic: bool = False
    branded_content: bool = False


class TikTokCreatorInfo(BaseModel):
    """`creator_info` as the composer needs it, plus what we know about our
    own audit state so the UI can be honest about what will happen."""

    nickname: str
    username: str
    avatar_url: str
    privacy_level_options: list[str]
    comment_disabled: bool
    duet_disabled: bool
    stitch_disabled: bool
    max_video_post_duration_sec: int
    # True while our TikTok client has not passed the content audit, when
    # TikTok refuses anything but a private post. Drives a warning, not a
    # silent override — the creator's choice is always sent as chosen.
    unaudited: bool


class PublishCreate(BaseModel):
    social_account_id: uuid.UUID
    caption: str = Field(default="", max_length=2200)
    # Required when the target account is TikTok; ignored for other platforms.
    tiktok: TikTokOptions | None = None


# ---------- billing ----------
class PlanChangeResponse(BaseModel):
    plan: str
    cancel_at_period_end: bool
    message: str


# ---------- analytics ----------
class EventIn(BaseModel):
    name: str = Field(max_length=64)
    props: dict = {}
