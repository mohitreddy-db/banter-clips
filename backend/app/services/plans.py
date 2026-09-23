"""Plan capabilities — what a plan buys, as opposed to credits (the fuel).

PRICING.md §5. Kept in one place so the API gates and the copy agree.
Prompt length is a capability: 280 characters on Free, 500 on Creator.
1080p, 30-second videos, watermark-free output and downloads are gated in
the clips router and frozen per clip at creation.
"""

FREE_TAKE_CHARS = 280
CREATOR_TAKE_CHARS = 500


def is_creator(plan: str | None) -> bool:
    return str(plan or "").lower() == "creator"


def take_limit(plan: str | None) -> int:
    return CREATOR_TAKE_CHARS if is_creator(plan) else FREE_TAKE_CHARS
