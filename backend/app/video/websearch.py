"""Web search for the research features — Firecrawl first, OpenAI as fallback.

Four features need "what is true on the internet right now": the Viral
trending feed, the Storyline Pack, off-catalog cast research, and the
catalog verifier. They all ask the same shape of question — a JSON-returning
prompt answered from live search results — so they share this one module.

Two ways to get there:

- FIRECRAWL (preferred, `FIRECRAWL_API_KEY`): run one or more searches on
  Firecrawl, bundle the source-backed results (title, URL, snippet, date and
  optionally a page excerpt) and have the plain research model answer the
  prompt ONLY from them. Search and reasoning are separate calls, which is
  cheaper, faster to debug, and never lets the model "remember" a result.
- OPENAI `web_search` (fallback, `WEB_RESEARCH=openai`): the Responses API
  with its built-in search tool, exactly as before Firecrawl existed.

Never raises. A Firecrawl 401 marks the key bad for the process lifetime so
a wrong key degrades to the fallback once, not on every call.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

import httpx

from ..config import settings

log = logging.getLogger("banter.video.websearch")

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
RECENT = {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m"}
SNIPPET_CHARS = 300
EXCERPT_CHARS = 1500
MAX_SOURCES = 14

_key_rejected = False   # set after a 401 — Firecrawl is skipped afterwards


@dataclass
class Hit:
    title: str = ""
    url: str = ""
    snippet: str = ""
    date: str = ""
    excerpt: str = ""    # page markdown, when the search scraped it

    def block(self, n: int) -> str:
        head = f"[{n}] {self.title} — {self.url}" + (f" ({self.date})" if self.date else "")
        body = self.snippet
        if self.excerpt:
            body += f"\n    excerpt: {self.excerpt}"
        return f"{head}\n    {body}".rstrip()


@dataclass
class SearchSpec:
    """One Firecrawl query. `scrape_top` fetches page markdown for the first
    N results — facts like a kit sponsor wordmark rarely fit in a snippet."""
    query: str
    limit: int = 8
    recent: str | None = None          # "day" | "week" | "month"
    scrape_top: int = 0
    sources: tuple[str, ...] = ("web", "news")


def firecrawl_enabled() -> bool:
    return bool(getattr(settings, "FIRECRAWL_API_KEY", "")) and not _key_rejected


def openai_search_enabled() -> bool:
    return (getattr(settings, "WEB_RESEARCH", "off") == "openai"
            and bool(getattr(settings, "OPENAI_API_KEY", "")))


def enabled() -> bool:
    """Any web research at all. `WEB_RESEARCH=off` is the master switch."""
    if str(getattr(settings, "WEB_RESEARCH", "off")).lower() == "off":
        return False
    return firecrawl_enabled() or openai_search_enabled()


# ---------------------------------------------------------------- firecrawl

def search(spec: SearchSpec) -> list[Hit]:
    """One Firecrawl search. Empty on any failure."""
    global _key_rejected
    if not firecrawl_enabled():
        return []
    body: dict = {"query": spec.query, "limit": max(1, min(20, spec.limit)),
                  "sources": list(spec.sources)}
    if spec.recent in RECENT:
        body["tbs"] = RECENT[spec.recent]
    if spec.scrape_top > 0:
        body["scrapeOptions"] = {"formats": ["markdown"]}
    base = str(getattr(settings, "FIRECRAWL_URL", "https://api.firecrawl.dev")).rstrip("/")
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(
                f"{base}/v2/search", json=body,
                headers={"Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}"},
            )
    except Exception:  # noqa: BLE001 — search is a bonus, never a blocker
        log.exception("firecrawl search failed")
        return []
    if resp.status_code == 401:
        _key_rejected = True
        log.error("firecrawl rejected the API key (401) — falling back to OpenAI web_search")
        return []
    if resp.status_code >= 400:
        log.warning("firecrawl search -> %s %s", resp.status_code, resp.text[:300])
        return []
    try:
        payload = resp.json()
    except ValueError:
        return []
    hits = parse_results(payload)
    if spec.scrape_top > 0:
        for hit in hits[spec.scrape_top:]:
            hit.excerpt = ""
    return hits


def parse_results(payload: dict) -> list[Hit]:
    """Firecrawl's search payload, v2 ({"data": {"web": [...], "news": [...]}})
    or v1 ({"data": [...]}), into hits — news first, since it carries dates."""
    data = payload.get("data") if isinstance(payload, dict) else None
    raw: list = []
    if isinstance(data, dict):
        for key in ("news", "web"):
            raw.extend(x for x in (data.get(key) or []) if isinstance(x, dict))
    elif isinstance(data, list):
        raw.extend(x for x in data if isinstance(x, dict))
    hits: list[Hit] = []
    seen: set[str] = set()
    for item in raw:
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        hits.append(Hit(
            title=str(item.get("title") or "").strip()[:160],
            url=url[:300],
            snippet=re.sub(r"\s+", " ", str(item.get("description") or item.get("snippet") or "")).strip()[:SNIPPET_CHARS],
            date=str(item.get("date") or item.get("publishedDate") or "").strip()[:40],
            excerpt=re.sub(r"\s+", " ", str(item.get("markdown") or "")).strip()[:EXCERPT_CHARS],
        ))
    return hits


# ---------------------------------------------------------------- the question

@dataclass
class Answer:
    data: dict | None = None
    provider: str = ""                 # "firecrawl" | "openai" | ""
    sources: list[Hit] = field(default_factory=list)


def ask(prompt: str, specs: list[SearchSpec], *, timeout: float = 60.0,
        max_tokens: int = 2500) -> Answer:
    """Answer a JSON-shaped research prompt from the live web.

    Firecrawl path: run the specs, bundle the hits, and let the research
    model answer strictly from them. Nothing found (or no key) → the OpenAI
    web_search path, exactly the pre-Firecrawl behaviour."""
    if firecrawl_enabled():
        hits: list[Hit] = []
        seen: set[str] = set()
        for spec in specs:
            for hit in search(spec):
                if hit.url not in seen:
                    seen.add(hit.url)
                    hits.append(hit)
        hits = hits[:MAX_SOURCES]
        if hits:
            data = _answer_from_sources(prompt, hits, max_tokens=max_tokens)
            if data is not None:
                return Answer(data=data, provider="firecrawl", sources=hits)
    if openai_search_enabled():
        data = _ask_openai_search(prompt, timeout=timeout)
        return Answer(data=data, provider="openai" if data is not None else "")
    return Answer()


SOURCES_SYSTEM = """\
You are a careful sports researcher. You will get a task and a numbered list
of live search results. Answer the task ONLY from those results — never from
memory, never by guessing. If the results do not support a fact, leave it
out (empty string / empty list). Return ONLY the JSON the task asks for."""


def _answer_from_sources(prompt: str, hits: list[Hit], *, max_tokens: int) -> dict | None:
    from . import providers

    key = getattr(settings, "OPENAI_API_KEY", "")
    if not key:
        return None
    client = providers.TextClient(key, getattr(settings, "OPENAI_RESEARCH_MODEL", "gpt-4.1-mini"))
    block = "\n".join(h.block(i + 1) for i, h in enumerate(hits))
    user = (f"TASK:\n{prompt}\n\nSEARCH RESULTS (live, source-backed, freshest first):\n{block}\n\n"
            f"Use only these results. Return only the JSON.")
    raw = client.complete_json(SOURCES_SYSTEM, user, max_tokens=max_tokens, temperature=0.2)
    return loads(raw)


def _ask_openai_search(prompt: str, *, timeout: float) -> dict | None:
    body = {
        "model": getattr(settings, "OPENAI_RESEARCH_MODEL", "gpt-4.1-mini"),
        "tools": [{"type": "web_search"}],
        "input": prompt,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                OPENAI_RESPONSES_URL, json=body,
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            )
    except Exception:  # noqa: BLE001
        log.exception("openai web_search call failed")
        return None
    if resp.status_code >= 400:
        log.warning("openai web_search -> %s %s", resp.status_code, resp.text[:300])
        return None
    texts: list[str] = []
    for item in resp.json().get("output") or []:
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("text"):
                texts.append(str(part["text"]))
    return loads("\n".join(texts))


def loads(text: str | None) -> dict | None:
    """The first JSON object in a model reply, or None."""
    if not text:
        return None
    text = str(text).strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None
