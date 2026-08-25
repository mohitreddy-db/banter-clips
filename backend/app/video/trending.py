"""Trending feed for the create page — what the internet is arguing about
RIGHT NOW in a sport, turned into ready-to-shoot takes.

Two stages, deliberately:

1. SWEEP — one web-search call (the same OpenAI `web_search` tool the
   Storyline Pack uses) ranks the last ~48 hours of that sport: results,
   moments, transfers, memes, controversies. Facts only, source-backed.
2. WRITE — a second, cheap text call turns each topic into two takes in the
   BanterClips voice (the TAKE_ENHANCER rules: front-loaded hook, named
   people, a filmable scene), each with a suggested tone and length. Search
   models report well but write banter badly; splitting the jobs is what
   makes the suggestions usable as-is.

One cached feed per sport (TTL below), shared by every user, so the cost is
a few cents per sport per hour no matter how many people open the page.
Never raises: no key, a bad response or a timeout yields the stale feed if
one exists, else an empty feed the UI hides.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone

import httpx

from ..config import settings

log = logging.getLogger("banter.video.trending")

RESPONSES_URL = "https://api.openai.com/v1/responses"
TTL = timedelta(minutes=20)
TOPICS = 5
PROMPTS_PER_TOPIC = 2

SWEEP_PROMPT = """\
Search the web for what {sport} fans are talking about RIGHT NOW.
Today's date: {today}. Look at the last 24-48 hours only: results and
moments from actual games, transfers/trades and rumours, records,
controversies, press-conference quotes, and whatever fans are memeing.

Return ONLY a JSON object, no prose:

{{"found": true/false,
  "topics": [
    {{"title": "the story in fan-speak, under 60 characters",
      "summary": "one factual sentence on what actually happened",
      "why_now": "why it is blowing up today, one short clause",
      "heat": "viral" | "hot" | "rising",
      "who": ["1-3 real people at the centre of it, most famous first"],
      "team": "club/franchise name or empty"}}
  ]}}

Rules: exactly {n} topics, ordered hottest first, each a DIFFERENT story
(different teams/people where possible). Only include what search results
support — never invent scores, quotes or transfers. Skip tragedies, deaths,
ongoing legal cases and anything fans would find tasteless to joke about.
If nothing current is found, return {{"found": false}}."""

WRITE_SYSTEM = """\
You write takes for BanterClips: an app that turns a fan's hot take into a
short AI comedy video. You will get today's trending topics in {sport}.
For each topic, write {k} DIFFERENT ready-to-post takes.

Rules for every take:
- Under 240 characters, first person, sounds like a fan in a group chat —
  confident, funny, a little unhinged. Never like a headline or a brand.
- Front-load the hook: the first five words carry the claim.
- Name the real people/team from the topic. Specific beats abstract.
- Make it VISUAL — it becomes a comedy video, so imply a scene someone
  could film (a person doing something absurd), not an abstract judgement.
- The two takes must attack the topic from different angles (e.g. one
  roasts the loser, one crowns the winner; one is a wild prediction).
- No hashtags, no emojis, no quotation marks around the whole take.
- tone is exactly one of: Funny, Savage, Hype, Bold — whichever fits.
- seconds is 10, 15 or 30: 10 for one-joke zingers, 15 for most, 30 only
  when the story genuinely has acts.
- angle is a 2-4 word label for the angle taken.

Return ONLY JSON:
{{"topics": [{{"index": <topic index>,
  "prompts": [{{"take": "...", "tone": "...", "seconds": 15,
                "angle": "..."}}]}}]}}"""


def enabled() -> bool:
    return (
        getattr(settings, "WEB_RESEARCH", "off") == "openai"
        and bool(getattr(settings, "OPENAI_API_KEY", ""))
    )


def get_feed(sport: str) -> dict:
    """The trending feed for a sport: {"topics": [...], "fetched_at": iso}.

    Served from the shared cache while fresh; refetched when stale. A failed
    refetch falls back to the stale feed rather than an error — old trending
    beats no trending."""
    sport = (sport or "NBA").strip()[:24]
    if not enabled():
        return {"topics": [], "fetched_at": None}
    row = _cache_get(sport)
    now = datetime.now(timezone.utc)
    if row is not None:
        fetched_at, pack = row
        if now - fetched_at < TTL:
            return {**pack, "fetched_at": fetched_at.isoformat()}
    try:
        pack = _build(sport)
    except Exception:  # noqa: BLE001 — trending is a bonus, never a blocker
        log.exception("trending build failed for %s", sport)
        pack = None
    if pack:
        _cache_put(sport, pack)
        return {**pack, "fetched_at": now.isoformat()}
    if row is not None:  # stale beats empty
        fetched_at, stale = row
        return {**stale, "fetched_at": fetched_at.isoformat()}
    return {"topics": [], "fetched_at": None}


# ------------------------------------------------------------------ pipeline

def _build(sport: str) -> dict | None:
    topics = _sweep(sport)
    if not topics:
        return None
    _write_prompts(sport, topics)  # best-effort; topics stay usable without
    return {"topics": topics}


def _sweep(sport: str) -> list[dict] | None:
    """Stage 1: web search → ranked factual topics."""
    body = {
        "model": getattr(settings, "OPENAI_RESEARCH_MODEL", "gpt-4.1-mini"),
        "tools": [{"type": "web_search"}],
        "input": SWEEP_PROMPT.format(sport=sport, today=date.today().isoformat(), n=TOPICS),
    }
    with httpx.Client(timeout=75.0) as client:
        resp = client.post(
            RESPONSES_URL, json=body,
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
        )
    if resp.status_code >= 400:
        log.warning("trending sweep -> %s %s", resp.status_code, resp.text[:300])
        return None
    texts: list[str] = []
    for item in resp.json().get("output") or []:
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("text"):
                texts.append(str(part["text"]))
    match = re.search(r"\{.*\}", "\n".join(texts), re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not (isinstance(data, dict) and data.get("found") and data.get("topics")):
        return None
    topics = []
    for t in data["topics"][:TOPICS]:
        if not (isinstance(t, dict) and t.get("title")):
            continue
        topics.append({
            "title": str(t["title"])[:80],
            "summary": str(t.get("summary") or "")[:200],
            "why_now": str(t.get("why_now") or "")[:120],
            "heat": t.get("heat") if t.get("heat") in ("viral", "hot", "rising") else "hot",
            "who": [str(w)[:40] for w in (t.get("who") or [])[:3]],
            "team": str(t.get("team") or "")[:60],
            "prompts": [],
        })
    return topics or None


def _write_prompts(sport: str, topics: list[dict]) -> None:
    """Stage 2: the banter engine — fills topic["prompts"] in place."""
    from . import providers

    client = providers.text_client()
    if not client.available:
        return
    payload = json.dumps([
        {"index": i, "title": t["title"], "summary": t["summary"],
         "who": t["who"], "team": t["team"]}
        for i, t in enumerate(topics)
    ], ensure_ascii=False)
    raw = client.complete_json(
        WRITE_SYSTEM.format(sport=sport, k=PROMPTS_PER_TOPIC),
        f"Today's topics:\n{payload}", max_tokens=2500, temperature=0.9,
    )
    if not raw:
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return
    for entry in (data.get("topics") or []) if isinstance(data, dict) else []:
        try:
            topic = topics[int(entry["index"])]
        except (KeyError, ValueError, TypeError, IndexError):
            continue
        for p in (entry.get("prompts") or [])[:PROMPTS_PER_TOPIC]:
            take = str(p.get("take") or "").strip()
            if not take:
                continue
            topic["prompts"].append({
                "take": take[:280],
                "tone": p.get("tone") if p.get("tone") in ("Funny", "Savage", "Hype", "Bold") else "Funny",
                "seconds": int(p["seconds"]) if p.get("seconds") in (10, 15, 30) else 15,
                "angle": str(p.get("angle") or "")[:40],
            })


# --------------------------------------------------------------------- cache

def _cache_get(sport: str) -> tuple[datetime, dict] | None:
    from ..db import SessionLocal
    from ..models import TrendingPack

    db = SessionLocal()
    try:
        row = db.query(TrendingPack).filter(TrendingPack.sport == sport).first()
        if row is None:
            return None
        fetched = row.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return fetched, dict(row.pack)
    finally:
        db.close()


def _cache_put(sport: str, pack: dict) -> None:
    from ..db import SessionLocal
    from ..models import TrendingPack

    db = SessionLocal()
    try:
        row = db.query(TrendingPack).filter(TrendingPack.sport == sport).first()
        if row is None:
            db.add(TrendingPack(sport=sport, pack=pack))
        else:
            row.pack = pack
            row.fetched_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:  # noqa: BLE001 — a cache miss next time is the only cost
        log.warning("could not cache trending feed for %s", sport)
    finally:
        db.close()
