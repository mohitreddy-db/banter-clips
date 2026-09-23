"""Check the catalog against reality — `python -m app.video.catalog_verify`.

The catalog asserts specific facts now: which club someone plays for, their
squad number, what their kit looks like. Those go straight into a prompt and
get rendered as legible text, so a stale entry does not produce a vague video,
it produces a confidently wrong one — Messi in the wrong shirt, the wrong
number on the back. That is worse than the old vagueness, and it is the price
of the specificity that makes the frames look real.

Players transfer and clubs change kits every season, so this exists to tell
you WHICH entries have drifted. It deliberately does not rewrite anything:
web results are data, not instructions, and a curated catalog that a person
approved is the whole point. It prints a diff and you decide.

    python -m app.video.catalog_verify              # every character
    python -m app.video.catalog_verify messi ronaldo
    python -m app.video.catalog_verify --sport NBA
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys

from ..config import settings
from . import catalog, websearch
from .types import _clean

log = logging.getLogger("banter.video.verify")

VERIFY_PROMPT = """\
Search the web for the current status of the {sport} player "{name}".

Return ONLY JSON, no prose:

{{"found": true/false,
  "team": "their club or franchise RIGHT NOW",
  "number": "their current squad number as digits, or empty string",
  "kit": "one clause describing that club's current home kit",
  "changed_recently": "one short line if they transferred or changed number in the last year, else empty string"}}

Report what is true today, not what was true when they were most famous. If
you are not confident about the number, return an empty string — a wrong
number is worse than none."""


def _ask(name: str, sport: str) -> dict | None:
    answer = websearch.ask(VERIFY_PROMPT.format(name=name, sport=sport), [
        websearch.SearchSpec(f"{name} {sport} current club squad number", limit=6, recent="month", scrape_top=2),
    ], timeout=90.0, max_tokens=800)
    return answer.data


def check(char: catalog.Character) -> list[str]:
    """Differences worth a human look. Empty means the entry still holds."""
    data = _ask(char.name, char.sport)
    if not data or not data.get("found"):
        return ["could not verify"]

    notes: list[str] = []
    team = _clean(data.get("team"))
    if team:
        known = [catalog.get_team(t) for t in char.teams]
        known_names = " ".join((t.name.lower() for t in known if t))
        # Substring both ways: "Inter Miami CF" vs "Inter Miami" should match.
        if known_names and not any(
            w in known_names for w in team.lower().split() if len(w) > 3
        ):
            notes.append(f"team: catalog says {[t.id for t in known if t]}, web says {team!r}")

    number = re.sub(r"[^0-9]", "", str(data.get("number") or ""))
    if number and number not in char.default_wardrobe:
        notes.append(f"number: web says {number}, not found in wardrobe")

    changed = _clean(data.get("changed_recently"))
    if changed:
        notes.append(f"recent change: {changed[:90]}")
    return notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check catalog entries against the web")
    parser.add_argument("ids", nargs="*", help="character ids (default: all)")
    parser.add_argument("--sport", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    if not getattr(settings, "OPENAI_API_KEY", ""):
        print("OPENAI_API_KEY is not set — verification needs it.")
        return 1

    chars = catalog.characters()
    targets = [chars[i] for i in args.ids if i in chars] if args.ids else list(chars.values())
    if args.sport:
        targets = [c for c in targets if c.sport == args.sport]
    # Archetypes ("a weary head coach") have nothing to verify.
    targets = [c for c in targets if not c.name.lower().startswith(("a ", "an ", "the "))]

    print(f"checking {len(targets)} character(s)…\n")
    drifted = 0
    for char in sorted(targets, key=lambda c: (c.sport, c.id)):
        try:
            notes = check(char)
        except Exception:  # noqa: BLE001 — one failure must not stop the sweep
            log.exception("verify failed for %s", char.id)
            notes = ["verification errored"]
        if notes:
            drifted += 1
            print(f"  {char.sport:<7} {char.id}")
            for n in notes:
                print(f"      - {n}")
        else:
            print(f"  {char.sport:<7} {char.id:<14} ok")

    print(f"\n{drifted} of {len(targets)} need a look. "
          f"Nothing was changed — edit catalog/characters.json yourself.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
