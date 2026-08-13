"""Keyframe review — the cheap gate before the expensive step.

A still costs a few cents; animating it costs orders of magnitude more. So
every spend decision is made here, on the still.

Severity matters. An early binary version of this gate failed *every*
candidate, because near-perfect hands are rare in generated images and it
treated slightly odd fingers the same as a brand logo. Split the checks:

  hard  — GARBLED lettering, collages, non-photoreal medium, severe anatomy.
          Regenerate.

Note what is no longer a failure: visible text and real logos. A measured A/B
found the model renders "SPURS 1" cleanly when asked for the real kit, and
renders jersey-shaped gibberish when told a jersey must carry no lettering.
Banning text caused the garbling it was meant to prevent, and rejecting every
frame containing text threw away the good ones too. The gate now judges the
QUALITY of lettering rather than its presence.
  soft  — hands, minor anatomy, background oddities, subject doubt. Note it
          and move on. (`subject_matches` is soft because it measured noisy:
          it rejected correct frames of the intended players.)

Without that split the retry budget is spent on frames that were fine.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

log = logging.getLogger("banter.video.review")

SYSTEM = """\
You are a quality gate for AI-generated sports-comedy keyframes.
Judge only what is visible. Return ONLY JSON with exactly these keys:

{"visible_text": "<every word, letter or number you can read in the image, or NONE>",
 "has_garbled_text": true/false,
 "has_real_logo": true/false,
 "subject_matches": true/false,
 "is_single_frame": true/false,
 "is_photoreal": true/false,
 "medium": "<photograph | illustration | cartoon | 3d_render | painting | other>",
 "minor_defects": "<odd hands, small anatomy or background issues, or NONE>",
 "severe_defects": "<extra limbs, melted or duplicated faces, impossible bodies, or NONE>",
 "lower_quarter_clean": true/false}

has_garbled_text judges the QUALITY of lettering, not its presence. Real kit
names, squad numbers, club crests, sponsor boards and arena signage are all
expected and wanted — they are what makes the frame look like real footage.

Set has_garbled_text true ONLY when visible lettering is malformed: invented
non-words ("RUACIS" where "SPURS" belongs), mirrored or upside-down glyphs,
letters that dissolve into shapes, inconsistent typefaces within one word, or
numbers that are not numbers. Correctly spelled, cleanly rendered text is a
pass however much of it there is.

Judge hands under minor_defects unless a limb is duplicated or missing, which
is severe.

is_single_frame is false if the image is a collage, split screen, grid,
storyboard, or otherwise shows the same scene from two camera positions
stacked or side by side. A single photograph is true. Look for horizontal or
vertical dividing lines separating different shots.

is_photoreal is true ONLY for something that could plausibly be a real
photograph of real people: real skin texture and pores, real fabric weave,
real optical depth of field and lighting. It is FALSE for cartoons, anime,
comic art, 3D or game-engine renders, digital paintings, illustrations,
cel-shaded or flat-shaded art, and any image with outlines, posterised
shading or simplified faces. A stylised colour grade on a real photograph is
still photoreal; a drawing of a person is not, however detailed."""


class Verdict:
    """Outcome of one review. Truthy when the frame is good enough to animate."""

    def __init__(self, ok: bool, hard: list[str], soft: list[str], raw: dict | None = None):
        self.ok, self.hard, self.soft = ok, hard, soft
        self.raw = raw or {}

    def __bool__(self) -> bool:
        return self.ok

    @property
    def reason(self) -> str:
        return "; ".join(self.hard) or "; ".join(self.soft) or "clean"

    def to_dict(self) -> dict:
        return {"ok": self.ok, "hard": self.hard, "soft": self.soft, "raw": self.raw}


def review_keyframe(path: Path, subject: str, client) -> Verdict:
    """Never raises. An unavailable reviewer passes the frame through.

    Passing through is deliberate: a broken review step must not block every
    job. The deterministic checks later still guard the final file.
    """
    if client is None or not getattr(client, "available", False):
        return Verdict(True, [], ["review skipped: no reviewer configured"])
    if not path or not Path(path).exists():
        return Verdict(False, ["keyframe missing"], [])

    try:
        b64 = base64.b64encode(Path(path).read_bytes()).decode()
        user = (
            f"The intended subject is: {subject}. "
            "Inspect this keyframe and return the JSON described."
        )
        raw = client.complete_json(SYSTEM, user, image_b64=b64)
        data = _loads(raw)
    except Exception:  # noqa: BLE001
        log.exception("keyframe review failed")
        return Verdict(True, [], ["review errored; frame accepted"])

    if not data:
        return Verdict(True, [], ["review unparseable; frame accepted"])

    hard, soft = [], []
    if _truthy(data.get("has_garbled_text")):
        found = str(data.get("visible_text") or "").strip()
        detail = f": {found[:60]}" if found and found.upper() != "NONE" else ""
        hard.append(f"garbled lettering{detail}")
    # Real crests, kit names and sponsor boards are wanted now — they are what
    # makes a frame read as broadcast footage. Only note them.
    if _truthy(data.get("has_real_logo")):
        soft.append("real logos visible (expected)")
    if data.get("subject_matches") is False:
        # Measured as noisy in both directions (it rejected correct frames of
        # Brunson and Wemby), so it warns instead of burning a retry (§8.2).
        soft.append("reviewer doubts the subject matches the brief")
    if data.get("is_single_frame") is False:
        # A collage cannot be animated — the clip inherits the panel layout.
        hard.append("not a single frame: collage or split screen")
    if data.get("is_photoreal") is False:
        # The clip inherits the still's medium, so one cartoon keyframe makes
        # one cartoon scene inside an otherwise photoreal video.
        medium = str(data.get("medium") or "stylised").strip()[:24]
        hard.append(f"not photoreal: rendered as {medium}")
    if _present(data.get("severe_defects")):
        hard.append(f"severe defect: {str(data['severe_defects'])[:70]}")

    if _present(data.get("minor_defects")):
        soft.append(f"minor: {str(data['minor_defects'])[:70]}")
    if data.get("lower_quarter_clean") is False:
        soft.append("lower quarter is busy")

    return Verdict(not hard, hard, soft, data if isinstance(data, dict) else {})


def _loads(text: str | None) -> dict | None:
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        brace = re.search(r"\{.*\}", text, re.S)
        if not brace:
            return None
        try:
            data = json.loads(brace.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1"}


def _present(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.upper() not in {"NONE", "NO", "N/A", "FALSE"}
