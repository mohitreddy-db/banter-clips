"""The credit wallet (PRICING.md).

One balance per user (`users.credits`), one append-only ledger
(`credit_entries`). Every change to the balance goes through `apply`, which
writes both in the same transaction — a balance that disagrees with its
ledger is the one bug this module exists to make impossible.

This file is the *seam* the mobile top-up needs. The full pricing model
(reservation on generation, charge on completion, refund on failure, monthly
grants) lives with the generation pipeline; `/billing/mobile/verify` only
needs `grant_topup`.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CreditEntry, User

log = logging.getLogger("banter.credits")

#: The packs on sale, from PRICING.md §6. Keys are shared with the web
#: top-up and with the store product ids (`credits_<key>`).
CREDIT_PACKS: dict[str, dict] = {
    "starter": {"name": "Starter", "credits": 100, "usd": 12.0, "popular": False},
    "creator": {"name": "Creator Pack", "credits": 300, "usd": 29.0, "popular": True},
    "pro": {"name": "Pro Pack", "credits": 750, "usd": 59.0, "popular": False},
    "studio": {"name": "Studio Pack", "credits": 2000, "usd": 129.0, "popular": False},
}


def apply(db: Session, user: User, delta: int, kind: str, *, note: str = "", clip_id=None) -> int:
    """Move the wallet by `delta` and record why. Returns the new balance.

    Locks the user row so two concurrent charges cannot both read the same
    balance. Never lets the balance go negative: a charge that would is a
    bug upstream (the price was quoted and reserved before the work began).
    """
    locked = db.scalar(select(User).where(User.id == user.id).with_for_update())
    current = int(locked.credits or 0) if locked is not None else int(user.credits or 0)
    balance = current + delta
    if balance < 0:
        raise ValueError(f"credit balance would go negative ({current} {delta:+})")
    (locked or user).credits = balance
    user.credits = balance
    db.add(
        CreditEntry(
            user_id=user.id,
            delta=delta,
            balance_after=balance,
            kind=kind,
            clip_id=clip_id,
            note=note or None,
        )
    )
    db.commit()
    return balance


def grant_topup(db: Session, user: User, pack: str) -> int:
    """Credit a purchased pack. Returns the credits added."""
    spec = CREDIT_PACKS[pack]
    apply(db, user, spec["credits"], "topup", note=f"pack {pack}")
    log.info("topup: user %s +%s credits (%s)", user.id, spec["credits"], pack)
    return spec["credits"]
