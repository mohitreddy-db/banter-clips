"""Data shapes passed between pipeline stages.

Everything here is permissive by construction: every field has a default, and
`from_raw` classmethods coerce whatever a model actually returned into a valid
object rather than rejecting it. A half-filled plan still renders a video.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

# 9:16 everywhere; the generator caps at 15s per clip.
MAX_SCENE_SECONDS = 15
MIN_SCENE_SECONDS = 2
# Spoken words land at roughly this rate, used to size dialogue to a scene.
WORDS_PER_SECOND = 2.2


def _clean(value: object, fallback: str = "") -> str:
    """Any scalar -> a trimmed single-line string."""
    if value is None:
        return fallback
    text = " ".join(str(value).split())
    return text or fallback


def _clamp(value: object, low: float, high: float, fallback: float) -> float:
    try:
        return max(low, min(high, float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


@dataclass
class CastMember:
    """Someone who appears on screen. `voice` is a delivery direction, not an id."""

    id: str = "subject"
    name: str = "the player"
    look: str = "a professional athlete in team kit"
    # Learned the hard way: naming the person keeps the likeness, and the
    # no-lettering rule is what keeps garbled text off the kit. Both are needed.
    wardrobe: str = "plain team-coloured kit with no lettering or numbers"
    voice: str = "neutral, conversational"

    @classmethod
    def from_raw(cls, raw: object, index: int = 0) -> CastMember:
        if isinstance(raw, str):
            return cls(id=_slug(raw) or f"cast_{index}", name=_clean(raw, "the player"))
        if not isinstance(raw, dict):
            return cls(id=f"cast_{index}")
        name = _clean(raw.get("name"), "the player")
        return cls(
            id=_clean(raw.get("id")) or _slug(name) or f"cast_{index}",
            name=name,
            look=_clean(raw.get("look"), cls.look),
            wardrobe=_clean(raw.get("wardrobe"), cls.wardrobe),
            voice=_clean(raw.get("voice"), cls.voice),
        )


@dataclass
class Scene:
    """One generated clip: a tableau with at most one speaker.

    The camera is split into four independent axes rather than one free-text
    blob, because that is how every current video model's prompting guide
    expects it (Veo, Sora, Kling all separate shot size / angle / movement /
    lens). A single "camera" string forced the model to guess which axis we
    meant, and produced shot *lists* — which is how a keyframe once came back
    as a three-panel collage.
    """

    index: int = 0
    beat: str = "hook"
    venue: str = "a packed stadium at night"
    action: str = "the subject reacts to the camera"

    # Camera, four axes. Kept separate so each can be defaulted independently.
    shot_size: str = "medium wide shot"
    camera_angle: str = "eye level"
    camera_move: str = "slow push-in"
    lens: str = "35mm, shallow depth of field"

    # Performance and world.
    expression: str = ""      # face and body language of the speaker
    blocking: str = ""        # where people are and how they move in frame
    lighting: str = ""
    beats: str = ""           # quantified micro-timing inside the clip
    sfx: str = ""             # one or two diegetic sounds
    transition: str = ""      # how this shot hands over to the next

    speaker_id: str = ""
    line: str = ""
    delivery: str = "deadpan"
    seconds: float = 7.0

    # Cinematography written by the shot writer, if it ran. Only the
    # descriptive body — the photoreal anchor, negatives and dialogue are
    # still appended deterministically, because a model that can delete a
    # guardrail eventually does.
    shot_prompt: str = ""

    # Kept for backwards compatibility with plans written before the camera
    # was split apart; `camera` still reads as one line for prompts and logs.
    @property
    def camera(self) -> str:
        parts = [self.shot_size, self.camera_angle, self.camera_move]
        return ", ".join(p for p in parts if p)

    @classmethod
    def from_raw(cls, raw: object, index: int, default_venue: str) -> Scene:
        if not isinstance(raw, dict):
            return cls(index=index, venue=default_venue)
        # Older plans (and sloppy responses) put everything in one "camera"
        # string; use it as the shot size so nothing is lost.
        legacy = _clean(raw.get("camera"))
        return cls(
            index=index,
            beat=_clean(raw.get("beat"), "escalation"),
            venue=_clean(raw.get("venue") or raw.get("setting"), default_venue),
            action=_clean(raw.get("action"), cls.action),
            shot_size=_clean(raw.get("shot_size"), legacy or cls.shot_size),
            camera_angle=_clean(raw.get("camera_angle"), cls.camera_angle),
            camera_move=_clean(raw.get("camera_move"), cls.camera_move),
            lens=_clean(raw.get("lens"), cls.lens),
            expression=_clean(raw.get("expression")),
            blocking=_clean(raw.get("blocking")),
            lighting=_clean(raw.get("lighting")),
            beats=_clean(raw.get("beats") or raw.get("timing")),
            sfx=_clean(raw.get("sfx") or raw.get("sound")),
            transition=_clean(raw.get("transition")),
            speaker_id=_clean(raw.get("speaker_id") or raw.get("speaker")),
            line=_clean(raw.get("line") or raw.get("dialogue")),
            delivery=_clean(raw.get("delivery"), cls.delivery),
            seconds=_clamp(
                raw.get("seconds") or raw.get("duration_seconds"),
                MIN_SCENE_SECONDS, MAX_SCENE_SECONDS, cls.seconds,
            ),
        )

    def fits_line(self) -> bool:
        """Is the line short enough to be spoken inside the clip?"""
        return len(self.line.split()) <= self.seconds * WORDS_PER_SECOND + 1

    def trimmed_line(self) -> str:
        """Shorten an over-long line rather than letting it run past the cut.

        The cut lands on a sentence or clause boundary when one exists near
        the budget — a hard word-count chop produced spoken fragments like
        "just like the." (observed 2026-08-21), which is worse out loud than
        speech running slightly fast."""
        budget = int(self.seconds * WORDS_PER_SECOND)
        words = self.line.split()
        if len(words) <= budget:
            return self.line
        # Search backwards from just past the budget for a natural stop.
        for i in range(min(len(words), budget + 2), max(2, budget - 4), -1):
            candidate = " ".join(words[:i])
            if candidate.endswith((".", "!", "?", "—", ",")):
                return candidate.rstrip(",—").strip() or candidate
        return " ".join(words[:budget]).rstrip(",;:") + "."


@dataclass
class VideoPlan:
    """The full creative brief. Downstream stages read only this."""

    title: str = "Untitled take"
    take: str = ""
    sport: str = "NBA"
    tone: str = "Bold"
    # Burned into the top of every frame when set. Empty by default: the
    # product owner decides whether to label output, and the value comes from
    # VIDEO_DISCLOSURE so turning it back on is a config change, not a deploy.
    disclosure: str = ""
    style: str = ""
    focus: str = "generic"  # "player" | "team" | "matchup" | "generic"
    team_ids: list[str] = field(default_factory=list)
    cast: list[CastMember] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    source: str = "fallback"  # "llm" | "repaired" | "fallback"

    @property
    def total_seconds(self) -> float:
        return sum(s.seconds for s in self.scenes)

    def speaker_for(self, scene: Scene) -> CastMember | None:
        for member in self.cast:
            if member.id == scene.speaker_id:
                return member
        return self.cast[0] if self.cast else None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "VideoPlan":
        """Rebuild a plan stored as JSON (the script approval flow persists
        plans on the clip row between the script and render phases)."""
        raw = raw if isinstance(raw, dict) else {}
        cast = [CastMember(**{k: v for k, v in c.items()
                              if k in CastMember.__dataclass_fields__})
                for c in raw.get("cast", []) if isinstance(c, dict)]
        scenes = [Scene(**{k: v for k, v in s.items()
                           if k in Scene.__dataclass_fields__})
                  for s in raw.get("scenes", []) if isinstance(s, dict)]
        fields_ = {k: v for k, v in raw.items()
                   if k in cls.__dataclass_fields__ and k not in ("cast", "scenes")}
        return cls(cast=cast, scenes=scenes, **fields_)


@dataclass
class SceneAsset:
    """What actually got produced for one scene, and what it cost."""

    index: int
    keyframe_path: str | None = None
    clip_path: str | None = None
    transcript: str = ""
    review: dict = field(default_factory=dict)
    attempts: int = 0
    cost_usd: float = 0.0
    notes: list[str] = field(default_factory=list)
    ok: bool = False

    def note(self, message: str) -> None:
        self.notes.append(message)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")[:40]
