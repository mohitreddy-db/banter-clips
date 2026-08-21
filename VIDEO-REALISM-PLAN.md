# Video realism plan — closing the gap to the viral reference

2026-08-21. Source material: frame-by-frame analysis of the reference edit
("Mourinho's First Training Session at Real Madrid", 77.75s, 720×1264@60,
analyzed via shot-cut detection + 78 extracted frames), our own recent
outputs, and two research passes (web-context APIs; multi-shot generation
practice). This supersedes the shot-structure part of VIDEO-QUALITY-REVIEW.

---

## 1. What the reference actually is (frame-by-frame findings)

**Structure (measured):**
- 78 seconds, ONE location (a faithful Real Madrid Valdebebas-style
  training ground), one continuous scenario with a full sketch arc:
  stars arrive late at the gate → Mourinho checks his watch → scolding →
  excuses → punishment jog → line-up lecture → whistle → reactions.
- ~10–14 generation segments joined by soft crossfades and a few hard
  cuts. Long dialogue takes (5–10s) alternate with shorter reaction
  shots. Camera changes BETWEEN segments (wide → medium → close-up);
  the world never changes.
- **Continuity is total**: the gym bags dropped on the ground in minute 1
  are still there in minute 2, in the same spots. Background players keep
  training in the distance. Same harsh midday light throughout.
- **No burned captions at all.** The dialogue audio carries the video.
  60fps output (interpolated in post).

**Why it lands (the "wow" ingredients, in priority order):**

1. **It's a real storyline, played straight.** Mourinho (real RM history,
   famous disciplinarian, watch-tapping is HIS bit) meets the actual
   current squad — Mbappé, Vinicius, Bellingham, instantly recognizable.
   Fictional premise, 100% real context. The joke works because every
   detail is plausible.
2. **Cast contains ONLY people who belong.** Three stars + the manager.
   No random defender, no reporter holding a sign.
3. **Real branding everywhere**: "Emirates FLY BETTER" across every chest,
   adidas logos on shirts/boards/bags, the RM crest on the wall, the gate,
   the shorts, "Realmadrid" on the building, "THIS IS GRANDEZA" banner,
   "JM" initials embroidered on Mourinho's staff top, whistle on a lanyard.
   (Close inspection shows small typos — "FLY BETT2" — invisible at speed.)
4. **The venue is story-specific and mundane-real**: a training ground on
   a Tuesday, not "a packed stadium at night with confetti". Daylight,
   pavement, mannequins, goal frames.
5. **Persona-true physical comedy**: the watch tap, the punishment jog,
   hands-on-knees exhaustion, the whistle, the finger wag. Gags belong to
   the character, not generic "holds a banner".

## 2. Gap analysis — our pipeline vs the reference

| Dimension | Reference | Us today |
|---|---|---|
| Context | real squad, real manager beef, real kit/sponsor, current storyline | none — planner invents from the take alone |
| Cast | only people who belong | catalog-biased, generic filler characters |
| Location | one story-specific real place, persistent | 1–2 generic venue strings ("floodlit stadium at night") |
| Branding | real sponsors/crests/signage | actively BANNED (CLEAN_TEXT forbids sponsor text) |
| Structure | ~10 shots, one world, arc with beats | 2 "scenes", often 2 unrelated worlds |
| Shot length | 2–10s, varied; camera changes between shots | 5–10s fixed, one composition per scene |
| Captions | none — audio carries it | big burned captions on everything |
| Duration | 78s | 10–30s |
| Comedy | persona-true physical bits | prop/sign-based generic gags |

The single deepest cause: **our planner knows nothing about the real
world.** Everything else (wrong cast, generic venues, sterile branding,
sign-based jokes) flows from that.

## 3. The context layer (the big unlock)

Add a **context stage before planning**: given (take, sport, detected
teams/players, tone), fetch a **Storyline Pack** and hand it to the planner.

**Storyline Pack (JSON), cached per team/topic per day:**
```
{
  "entities": {players[], manager, club}, // who's actually involved NOW
  "recent": ["lost 2-0 to X on Saturday", "manager under pressure", ...],
  "storylines": ["fans joking that ...", "controversy about ..."],
  "kits": {"home": "white, Emirates FLY BETTER, adidas", "training": "..."},
  "places": ["Valdebebas training ground: white buildings, crest wall,
              adidas boards", "the Bernabéu tunnel", ...],
  "personas": {"mourinho": "watch-tapping disciplinarian, 'I prefer not
               to speak' pressers", ...},
  "banned": ["things that would read as fake or offensive"]
}
```

**Providers (researched):**
- **Layer 1 — facts, free:** ESPN's hidden JSON API (scoreboard, standings,
  per-team news headlines; free, no key) or API-Football free tier.
  Hallucination-proof scores/fixtures at $0.
- **Layer 2 — narrative:** we already run **OpenAI `web_search`** in prod
  (character research uses it). Same tool, new prompt: one call per pack
  (~$0.01–0.03), returns storylines/memes/kit facts with citations.
  Dedicated upgrade later: **Linkup standard** ($0.005/call, 1–3s,
  `structured` output returns exactly the pack schema, $20/mo free credit
  covers MVP volume) or **Perplexity sonar via our OpenRouter key**.
- **Caching:** packs live in a DB table keyed (sport, team/topic, date);
  a hot take about Arsenal reuses today's Arsenal pack. Cost rounds to
  zero at MVP volume; latency amortizes to ~0 on cache hits.

The catalog stays the *likeness* layer (who people look like); the pack is
the *now* layer (what's true this week). Character research already proved
the pattern — this generalizes it from one person to the whole story.

## 4. Structure: from "2 scenes" to "one world, many shots"

Research verdict: Grok Imagine has **no reliable in-clip cut syntax**
(community timestamp hacks morph more often than they cut) and a 15s/call
cap with a 4–8s quality sweet spot. Viral creators get fast pacing by
generating **many short clips and cutting in post** — exactly what our
ffmpeg assembly already does. So:

- **Plan = one location + a shot list**, not N independent scenes.
  A 15s video becomes **1 anchor shot (6–8s, the dialogue/lip-sync
  moment) + 2–3 cutaways (2.5–4s: reactions, the physical gag, the
  detail insert)** — 3 hard cuts ≈ real reel pacing. 30s = ~6–8 shots
  with two dialogue anchors.
- **One world, enforced**: single venue description (from the Storyline
  Pack's `places`), identical across every shot; persistent props stated
  identically ("three black adidas gym bags on the pavement"); same
  time-of-day/light phrase everywhere.
- **Consistency mechanics per shot**: all keyframes derive from the
  scene-0 world anchor (already shipped) + character stills; the same
  identity phrase repeats verbatim in every prompt (already our rule);
  shot-specific framing changes, world text doesn't.
- Generating 4 short clips costs the same per second as 2 long ones;
  rerolling a bad 3s cutaway is cheap. Trim each to its best beat.
- **Later option:** Veo 3.1 is the only model with documented
  4-shots-in-8s timestamped prompting + audio across cuts — a natural
  candidate for the multi-model routing roadmap item.

## 5. Branding flip

CLEAN_TEXT currently bans everything unnamed — which also sterilized the
frames. New rule: **name it, don't ban it.**

- The Storyline Pack supplies the authentic strings: kit sponsor
  ("Emirates FLY BETTER"), maker marks (adidas/Nike), club name on
  buildings, staff-wear details ("JM initials", whistle).
- Prompts then NAME these on their surfaces (named text renders clean —
  our own measured rule). The ban stays only for surfaces nobody named.
- Accept small lettering imperfections in motion (the reference has them).
- ⚠️ Open business question, flagged not decided here: real sponsor/brand
  marks in AI parody raise trademark exposure beyond player likenesses.
  Ship behind a config flag; get a real opinion before public launch.

## 6. Cast discipline (extends the existing rule)

The planner rule "no roster stuffing" gets teeth from the pack: cast may
only contain (a) people the take names, (b) `entities` from the pack,
(c) at most one generic character WHEN the story needs a foil. If the
take names nobody and the pack is empty → one-character monologue format
(the safest funny format anyway).

## 7. Captions become a style choice

The reference burns no captions; the dialogue carries it. Our chunked
captions stay (publishing without sound matters on IG) but become
lighter: smaller, lower, word-grouped — and a per-clip "no captions"
toggle for the cinematic style. Default stays ON for reels.

## 8. Implementation order (each step independently shippable)

| # | Change | Effort | Expected effect |
|---|---|---|---|
| 1 | Storyline Pack service (ESPN facts + OpenAI web_search narrative, DB cache) + feed planner | M | context-aware scripts, right cast, right venue — the wow foundation |
| 2 | Planner: one-world shot-list format (anchor + cutaways), persistent-props rule, per-shot camera | M | pacing + continuity like the reference |
| 3 | Runner: per-shot generation (2.5–8s calls), trim-to-best, hard-cut assembly; venue/light lock | S–M | real edit rhythm; cheaper rerolls |
| 4 | Branding flip behind `AUTHENTIC_BRANDING` flag (pack-supplied strings) | S | frames read as real footage |
| 5 | Persona bits: pack `personas` → planner gag guidance | S | character-true comedy |
| 6 | Caption style options + off toggle | S | reference look available |
| 7 | 45–60s duration tier (Creator/credits) — the reference format is long | S after 2–3 | full sketch arc videos |
| 8 | A/B: Veo 3.1 for dialogue anchors (multi-model routing) | L | documented multi-shot + audio continuity |

**Measurement:** regenerate the same 4 review takes after steps 1–3 and
compare against the reference's ingredient list (§1): real cast only?
one persistent world? branding present? shot count ≥4? persona gag?
That checklist is the score.

## 9. Cost impact

Context: ~$0.01/video before caching, →~$0 cached. Structure: same
video-seconds, +2 keyframes (~$0.10) per video, minus cheaper rerolls.
Branding/persona: free (prompt-only). Net: within a few percent of
today's unit economics; credits pricing (PRICING.md) unaffected.
