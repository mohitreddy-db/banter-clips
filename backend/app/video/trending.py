"""Trending feed for the create page — what the internet is arguing about
RIGHT NOW in a sport, turned into ready-to-shoot takes.

Two stages, deliberately:

1. SWEEP — live web search (Firecrawl, with the OpenAI `web_search` tool as
   the fallback — see websearch.py) ranks the last ~48 hours of that sport:
   results, moments, transfers, memes, controversies. Facts only, source-backed.
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

from ..config import settings
from . import websearch

log = logging.getLogger("banter.video.trending")
TTL = timedelta(minutes=20)
# A user-triggered refresh may rebuild a pack this soon after the last build;
# inside the floor the cached pack is served with `refresh_after` set.
REFRESH_FLOOR = timedelta(minutes=3)
TOPICS = 5
PROMPTS_PER_TOPIC = 2

# The Viral tab's one-tap angles (Vikunja: "[MVP 1.5] Viral Presets tab").
# Every topic gets one take per angle, written in the same call as the
# free-form prompts; the label is built here so the client stays dumb.
PRESETS = (
    ("roast", "🔥", "Roast {target}",
     "ROAST: mock {target}'s performance or decisions from this story — mercilessly, never cruelly"),
    ("predict", "🔮", "Predict the season",
     "PREDICTION: state how this story ends for the season as settled fact, absurdly confident"),
    ("better", "⚖️", "Who is better?",
     "COMPARISON: pick a winner between the two sides/people in this story and defend it outrageously"),
    ("threat", "⚠️", "Biggest threat",
     "THREAT: name the one thing (a rival, a habit, a player) that will wreck them next, and why"),
    ("controversial", "🌶️", "Controversial take",
     "CONTROVERSY: the take most fans will furiously disagree with — pick the unpopular side"),
)

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

ALSO, for each topic, write one take per PRESET angle below — same rules,
but the angle is fixed and the take must commit to it completely:
{presets}

Return ONLY JSON:
{{"topics": [{{"index": <topic index>,
  "prompts": [{{"take": "...", "tone": "...", "seconds": 15,
                "angle": "..."}}],
  "presets": {{"roast": {{"take": "...", "tone": "...", "seconds": 15}},
              "predict": {{...}}, "better": {{...}}, "threat": {{...}},
              "controversial": {{...}}}}}}]}}"""


def enabled() -> bool:
    return websearch.enabled()


def get_feed(sport: str, force: bool = False) -> dict:
    """The trending feed for a sport: {"topics": [...], "fetched_at": iso,
    "refresh_after": seconds}.

    Served from the shared cache while fresh; refetched when stale. `force`
    (the Viral tab's refresh button) rebuilds early, but never inside
    REFRESH_FLOOR of the last build — that would let one impatient thumb
    bill a search per tap. A failed refetch falls back to the stale feed
    rather than an error — old trending beats no trending."""
    sport = (sport or "NBA").strip()[:24]
    if not enabled():
        return {"topics": [], "fetched_at": None, "refresh_after": 0}
    row = _cache_get(sport)
    now = datetime.now(timezone.utc)
    if row is not None:
        fetched_at, pack = row
        age = now - fetched_at
        fresh = age < TTL and _has_presets(pack)
        if fresh and not (force and refresh_allowed(fetched_at, now)):
            return {**pack, "fetched_at": fetched_at.isoformat(),
                    "refresh_after": _refresh_after(fetched_at, now)}
    try:
        pack = _build(sport)
    except Exception:  # noqa: BLE001 — trending is a bonus, never a blocker
        log.exception("trending build failed for %s", sport)
        pack = None
    if pack:
        _cache_put(sport, pack)
        return {**pack, "fetched_at": now.isoformat(),
                "refresh_after": int(REFRESH_FLOOR.total_seconds())}
    if row is not None:  # stale beats empty
        fetched_at, stale = row
        return {**stale, "fetched_at": fetched_at.isoformat(),
                "refresh_after": _refresh_after(fetched_at, now)}
    return {"topics": [], "fetched_at": None, "refresh_after": 0}


def refresh_allowed(fetched_at: datetime, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return now - fetched_at >= REFRESH_FLOOR


def _refresh_after(fetched_at: datetime, now: datetime) -> int:
    """Seconds until a forced refresh would rebuild; 0 when it would now."""
    return max(0, int((REFRESH_FLOOR - (now - fetched_at)).total_seconds()))


# ------------------------------------------------------------------ pipeline

def _build(sport: str) -> dict | None:
    topics = _sweep(sport)
    if not topics:
        return None
    _write_prompts(sport, topics)  # best-effort; topics stay usable without
    return {"topics": topics}


def _has_presets(pack: dict) -> bool:
    topics = pack.get("topics") or []
    return bool(topics) and all(t.get("presets") for t in topics)


def _preset_target(topic: dict) -> str:
    """Who a preset like "Roast {target}" is aimed at: the team, else the
    person at the centre of the story, else the story itself."""
    return (topic.get("team") or (topic.get("who") or [""])[0] or "them").strip()[:40]


def _sweep(sport: str) -> list[dict] | None:
    """Stage 1: web search → ranked factual topics."""
    prompt = SWEEP_PROMPT.format(sport=sport, today=date.today().isoformat(), n=TOPICS)
    answer = websearch.ask(prompt, [
        websearch.SearchSpec(f"{sport} news today", limit=8, recent="day"),
        websearch.SearchSpec(f"{sport} latest results controversy fans reaction", limit=8, recent="day"),
        websearch.SearchSpec(f"{sport} transfer trade rumours this week", limit=6, recent="week"),
    ], timeout=75.0, max_tokens=2500)
    data = answer.data
    if data is None:
        return None
    log.info("trending sweep for %s answered via %s (%d sources)",
             sport, answer.provider, len(answer.sources))
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
            "presets": [],
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
    preset_lines = "\n".join(f"- {key}: {brief}" for key, _icon, _label, brief in PRESETS)
    raw = client.complete_json(
        WRITE_SYSTEM.format(sport=sport, k=PROMPTS_PER_TOPIC, presets=preset_lines),
        f"Today's topics:\n{payload}", max_tokens=6000, temperature=0.9,
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
                "tone": _tone(p.get("tone")),
                "seconds": _seconds(p.get("seconds")),
                "angle": str(p.get("angle") or "")[:40],
            })
        # One-tap presets, in the fixed order the Viral tab shows them.
        written = entry.get("presets") if isinstance(entry.get("presets"), dict) else {}
        target = _preset_target(topic)
        presets = []
        for key, icon, label, _brief in PRESETS:
            p = written.get(key) if isinstance(written.get(key), dict) else None
            take = str((p or {}).get("take") or "").strip()
            if not take:
                continue
            presets.append({
                "key": key, "icon": icon,
                "label": label.format(target=target),
                "take": take[:280],
                "tone": _tone(p.get("tone"), default="Savage" if key == "roast" else "Bold"),
                "seconds": _seconds(p.get("seconds")),
            })
        topic["presets"] = presets


def _tone(value, default: str = "Funny") -> str:
    return value if value in ("Funny", "Savage", "Roast", "Hype", "Bold") else default


def _seconds(value) -> int:
    return int(value) if value in (10, 15, 30) else 15


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
