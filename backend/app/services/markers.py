"""Demo markers inside a take.

Two escape hatches that let anyone exercise the product end to end without
spending money or waiting minutes, including against production:

    [mock]  simulate the whole run — real stages, real pacing, no generation
    [fail]  fail during scene generation, to demo the failure + free retry

Rules that make these safe to keep in production:

1. The marker is stripped from the stored take, so it never appears in the
   video, the captions, or a published caption.
2. A clip produced from a marker is flagged `is_simulated`, and publishing a
   simulated clip is refused — a demo can never reach a real audience.
3. Simulated clips do not consume the monthly allowance.

Kept deliberately boring: substring matching, no regex, case-insensitive.
"""

from __future__ import annotations

MOCK = "[mock]"
FAIL = "[fail]"
ALL = (MOCK, FAIL)

# A take must survive the database's 10-character minimum after stripping.
MIN_TAKE_CHARS = 10
PADDING = " (demo run)"


def has(take: str | None, marker: str) -> bool:
    return marker in (take or "").lower()


def is_simulated(take: str | None) -> bool:
    """Should this run be simulated rather than generated?"""
    return has(take, MOCK)


def strip(take: str | None) -> str:
    """Remove every marker, leaving a take that still satisfies the schema."""
    text = take or ""
    lowered = text.lower()
    for marker in ALL:
        while marker in lowered:
            start = lowered.index(marker)
            text = text[:start] + text[start + len(marker):]
            lowered = text.lower()
    text = " ".join(text.split())
    if len(text) < MIN_TAKE_CHARS:
        # Stripping can leave too little for the clips_take_len constraint.
        text = (text + PADDING).strip()
    return text[:500]
