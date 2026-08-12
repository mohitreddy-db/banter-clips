# BanterClips — Detailed Video Generation Plan

**Version:** 1.2 · **Companion to** `BRD.md` (v2.2)  
**Goal:** Produce high-quality, detailed, cinematic 9:16 vertical sports-comedy videos that use **real player likenesses** and **team identity** (colors, associated players, contextual venues), feel polished enough to publish, and stay cost-controlled.

This document is the single source of truth for *how* videos are produced.

---

## 1. Product Goal (Quality Bar)

Every finished video must feel like a short, professional sports-comedy sketch:

- Real, recognisable athletes in exaggerated fictional situations.
- When the take is about a **team**, the video must feel like that team: correct color palette, players from that roster, venues and props that match the franchise context.
- Recurring cast (2 leads almost every scene + rotating support).
- Persistent world within a video (same pitch / tunnel / locker room reused).
- Dialogue-driven (characters speak to each other, not a narrator).
- Escalating absurdity that lands on a clear payoff.
- Clean, broadcast-grade look: sharp faces, correct proportions, no text defects, no official logos/crests, no collages.
- Native audio (dialogue + ambient crowd) loudness-normalised and clear.
- Burned-in animated captions + permanent AI/parody disclosure.
- Final output always **1080×1920, 30 fps, H.264/AAC, faststart MP4**.

The unit of production is a **scene**: one continuous comedic tableau with named characters saying lines.

---

## 2. Inputs & Defaults

| Input       | Allowed values                  | Default                          | Effect                                      |
|-------------|---------------------------------|----------------------------------|---------------------------------------------|
| `take`      | 10–280 characters               | generic sports opinion           | The opinion the story must preserve         |
| `sport`     | NBA · NFL · Soccer · MLB        | inferred from take, else NBA     | Selects roster + venue set                  |
| `tone`      | Funny · Savage · Hype · Bold    | Bold                             | Dialogue register + art direction           |
| `seconds`   | 15 · 30 · 60 · 90               | 15                               | Scene count + cost                          |
| `watermark` | on / off                        | on (free) / off (paid)           | Product watermark (AI disclosure always on) |

Nothing is required. Missing or invalid values are defaulted, inferred, or repaired.  
A job with zero arguments still produces a valid video.

**Scene count rule**  
`scenes = clamp(round(seconds / 7.5), 2, 12)`

| Duration | Scenes | Target seconds per scene |
|----------|--------|--------------------------|
| 15 s     | 2      | 7.5                      |
| 30 s     | 4      | 7.5                      |
| 60 s     | 8      | 7.5                      |
| 90 s     | 12     | 7.5                      |

Longer scenes look better than many short cuts.

---

## 3. Model Stack

| Stage              | Model / Tool                              | Endpoint / Method                          | Approx. cost (2026-08)          | Notes |
|--------------------|-------------------------------------------|--------------------------------------------|---------------------------------|-------|
| Story plan         | `gpt-4o-mini` (or Grok)                   | Chat completions, JSON mode                | < $0.01                         | Structured plan + repair |
| Keyframe image     | `x-ai/grok-imagine-image-quality`         | OpenRouter images API                      | **$0.05** each                  | High-detail stills |
| Keyframe review    | `gpt-4o-mini` + vision                    | Chat completions, JSON mode                | ~$0.01 each                     | Hard/soft fail gate |
| Animation          | `x-ai/grok-imagine-video-1.5`             | OpenRouter videos API (async)              | **$1.12** per 8 s @ 720p        | First-frame conditioned |
| Assembly           | ffmpeg                                    | Local                                      | free                            | Scale, loudnorm, concat, burn-ins |
| Fallback motion    | Ken Burns on keyframe                     | Local                                      | free                            | When video gen fails or budget exceeded |

**Key capability notes**
- Video model accepts `first_frame` only (no strong multi-image identity locking yet via OpenRouter).
- Audio is generated natively in the same video pass.
- `voice_id` pinning is currently unavailable → enforce one-speaker-per-scene.

**Economic argument**  
A still costs ~$0.05; a clip costs ~$1.12 (≈22×).  
All quality decisions happen on the still. Motion is only bought for frames that already passed review.

---

## 4. End-to-End Pipeline

```
take + sport + tone + seconds
        │
1. Resolve inputs              defaults · inference · clamping · safety          free
2. Detect focus                player / team / matchup / generic                 free
3. Story plan                  1 LLM call → JSON → repair layer                  <$0.01
4. Assign voices               alternate speakers across scenes                  free
5. Resolve cast + team         catalog lookup + color palette + references       free
6. Keyframe per scene          Grok image (≤2 attempts) + vision review          $0.05–0.12 each
7. Animate per scene           Grok video conditioned on approved keyframe       $1.12 each
8. Assemble                    scale · loudnorm · concat · captions · disclosure free
9. Validate                    duration · dimensions · codecs · audio            free
```

Progress UI stages:  
`planning_story` → `creating_voice` → `designing_characters` → `generating_scenes` → `animating_scenes` → `assembling_video` → `validating`.

---

## 5. Character & Team Catalog

### 5.1 Design principles

- Real player likenesses are allowed (under AI/parody disclosure).
- Team identity is expressed through **players belonging to the team**, **solid color palettes**, and **contextual venues** — never through official logos or readable text on clothing.
- Reference images are **AI-generated** (not real photos) for legal simplicity, consistency, and wardrobe control.
- Catalog stays small and high-quality (start with 8–12 strong characters per sport).

### 5.2 Storage layout

```
backend/app/video/catalog/
├── characters.json
├── teams.json
├── references/                  # AI-generated stills
│   ├── wembanyama_face_01.jpg
│   ├── wembanyama_full_01.jpg
│   ├── ronaldo_face_01.jpg
│   └── ...
└── README.md
```

### 5.3 Character entry schema

```json
{
  "id": "ronaldo",
  "name": "Cristiano Ronaldo",
  "sport": "Soccer",
  "teams": ["al-nassr"],
  "aliases": ["cr7", "cristiano", "ronaldo"],
  "look": "Athletic muscular build, short dark hair with faded sides, sharp jawline, intense focused eyes, light stubble, Portuguese features",
  "default_wardrobe": "plain solid-color soccer jersey with no numbers, no logos, no lettering; matching shorts; cleats",
  "voice_style": "Confident, slightly accented, declarative and intense",
  "reference_images": [
    "references/ronaldo_face_01.jpg",
    "references/ronaldo_full_01.jpg"
  ],
  "active": true
}
```

### 5.4 Team entry schema

```json
{
  "id": "spurs",
  "name": "San Antonio Spurs",
  "sport": "NBA",
  "aliases": ["spurs", "san antonio"],
  "primary_colors": ["black", "silver", "white"],
  "secondary_colors": ["dark gray"],
  "jersey_description": "solid black or silver basketball jersey with no logos, no numbers, no lettering",
  "venues": [
    "Spurs practice facility hallway",
    "AT&T Center player tunnel",
    "Spurs locker room"
  ],
  "associated_players": ["wembanyama"],
  "active": true
}
```

### 5.5 Why no numbers or names on jerseys

Current image models (including Grok) still produce garbled lettering frequently.  
Measured earlier: 3 of 4 scenes had text defects on first attempt when text was requested.

**Rule:** Jerseys are always described as solid team colors with the explicit phrase  
`no numbers, no logos, no lettering`.

Dialogue and burned-in captions can freely name the player and number. Only the visual jersey stays text-free.

### 5.6 Reference images — what to store

Generate **AI stills** (not real photos) once per important player:

1. Face close-up (neutral expression, clean lighting)
2. Full-body or three-quarter (clear proportions)
3. Optional side / ¾ view

Generation rules for references:
- Same Grok image model used in production
- Neutral studio lighting, clean background
- Plain solid-color jersey (the exact style we want)
- No logos, numbers, or text
- High facial and body detail

These images become permanent catalog assets. Regenerate only when a significantly better image model arrives.

### 5.7 Runtime lookup (how the system picks references)

```
1. Planner emits character IDs
2. System looks up each ID in characters.json
3. Pulls the stored reference_images list for that character
4. Selects 1–2 images according to simple rules:
   - Close-up camera → prefer face reference
   - Full-body / action → prefer full-body reference
   - Default → first 1–2 images listed
5. Feeds those images + name + look description into the keyframe prompt
```

If a character is missing from the catalog, fall back to pure text description (never fail the job).

---

## 6. How Identity Actually Works

The video model does **not** read the catalog. It only sees the text prompt and the first-frame image.

**Correct flow for “make Ronaldo do XYZ”:**

1. Resolve `ronaldo` from catalog → get name, look, reference images, team colors.
2. Generate a **keyframe still** using:
   - Name (“Cristiano Ronaldo”)
   - Detailed look description
   - Reference image(s) as visual anchors
   - Action + camera + clean jersey rules
3. **Validate** the keyframe (vision gate).
4. Only if it passes → send the approved keyframe as `first_frame` to the video model together with the motion prompt.
5. The video inherits the identity that was already locked in the still.

Pure text-to-video (“Ronaldo doing XYZ”) can work for extremely famous faces but is less consistent. The keyframe-first approach is the reliable method.

---

## 7. Team-Aware Generation

### 7.1 Focus detection

Before planning, classify the take:

| Focus type     | Examples                                      | Behaviour |
|----------------|-----------------------------------------------|---------|
| Player-focused | “Wemby is overrated”, “Messi still has it”    | Prioritise that exact player |
| Team-focused   | “The Lakers are frauds”, “Spurs rebuild…”     | Select players from that team + team colors + team venues |
| Matchup        | “Celtics vs Heat”, “Real Madrid will dominate”| Mix players from both sides, keep colors distinct |
| Generic        | “Refs are terrible this year”                 | Default sport roster + neutral venues |

### 7.2 How team identity appears

| Element        | Allowed                                      | Forbidden |
|----------------|----------------------------------------------|---------|
| Player faces   | Real likenesses of athletes on that team     | — |
| Jersey colors  | Solid colors matching the franchise palette  | Official logos, crests, wordmarks |
| Numbers/names  | None on clothing                             | Any readable text on jersey or boards |
| Venues         | Team-associated locations (no logos)         | Real stadium signage with team names |
| Dialogue       | Can freely name the team and players         | — |

---

## 8. System & Generation Prompts

### 8.1 Planner system prompt

```
You write short vertical sports-comedy videos. You turn one opinion into a
scene-by-scene plan.

Hard rules:
- Keep the user's stance. Sharpen it, exaggerate it, never reverse it.
- Exactly {scene_count} scenes, structured hook → escalation → payoff.
  Each escalation must RAISE the premise, never restate it.
- Each scene has AT MOST ONE speaker, and consecutive scenes must use
  DIFFERENT speakers. This is a hard technical constraint.
- A line must be speakable inside its scene: at most {max_words} words
  (max_words = seconds × 2.2).
- Cast only from the provided roster. Use their exact `id` values.
- When the take targets a team, prefer players who belong to that team and
  use the team’s color palette + venues. Still never invent logos or text.
- Comedy comes from a visual situation, not from wordplay. Describe what the
  camera literally sees.
- Never invent a factual result, score, or quote presented as real news.
- `camera` describes ONE camera position only — a single framing such as
  "low-angle medium shot" or "slow push-in on his face". Never a shot list.
- `style` describes ONLY look and lighting — lens, grade, mood.

Return ONLY JSON:
{
  "title": "...",
  "style": "...",
  "focus": "player" | "team" | "matchup" | "generic",
  "teams": ["..."],
  "cast": [{"id", "name", "look", "wardrobe", "voice"}],
  "scenes": [{
    "beat": "...",
    "venue": "...",
    "action": "...",
    "camera": "...",
    "speaker_id": "...",
    "line": "...",
    "delivery": "...",
    "seconds": number
  }]
}
```

### 8.2 Keyframe review system prompt

```
You are a quality gate for AI-generated sports-comedy keyframes.
Judge only what is visible. Return ONLY JSON with exactly these keys:

{
  "readable_text": bool,
  "has_text_defect": bool,
  "has_real_logo": bool,
  "subject_matches": bool,
  "is_single_frame": bool,
  "minor_defects": string[],
  "severe_defects": string[],
  "lower_quarter_clean": bool
}

has_text_defect means lettering is visible anywhere on clothing, boards or
signage — garbled or not. Judge hands under minor_defects unless a limb is
duplicated or missing, which is severe.

is_single_frame is false if the image is a collage, split screen, grid,
storyboard, or otherwise shows multiple camera positions.
```

**Hard fail (regenerate):** text defect · real logo · wrong subject · collage · severe anatomy.  
**Soft warn (continue):** odd hands · minor anatomy · busy lower quarter.  
`subject_matches` is currently noisy → treat as warning only.

### 8.3 Image prompt (assembled)

```
{STYLE_BIBLE}. {SINGLE_FRAME}. Setting: {venue}. 
Subjects: {name}, {look}, wearing {wardrobe}. 
Action: {action}. Framing: {first_shot(camera)}. 
Keep the lower quarter of the frame visually calm. 
{NEGATIVES}.
```

`wardrobe` is dynamically built from the team palette when applicable, always ending with  
`no numbers, no logos, no lettering`.

Reference images from the catalog are attached as visual anchors when the API supports it.

### 8.4 Motion prompt (assembled)

```
{STYLE_BIBLE}. Action: {action}. Camera: {camera}. 
Dialogue: {speaker}, {delivery}, says "{line}". 
Audio: ambient crowd noise under the dialogue. {NEGATIVES}.
```

### 8.5 Shared fragments

**STYLE_BIBLE**  
`Cinematic photoreal sports comedy, modern 35mm film look, shallow depth of field, bright broadcast lighting, vertical 9:16 composition, obvious visual comedy, highly detailed faces and fabric texture`

**NEGATIVES**  
`Absolutely no on-screen captions, subtitles, watermarks, brand logos, advertising boards, signage, scoreboards, crests, wordmarks, or readable text anywhere in the frame. No team logos. No collages or multi-panel layouts.`

**SINGLE_FRAME**  
`This is ONE single continuous photograph from ONE camera position: no split screen, no collage, no panels, no grid, no storyboard, no before-and-after, no multiple shots in the same image`

**TONE_DIRECTION**

| Tone   | Direction |
|--------|---------|
| Funny  | warm absurdist physical comedy; nobody is humiliated |
| Savage | sharp, cocky mockery aimed at the situation rather than personal dignity |
| Hype   | triumphant, loud, celebratory energy |
| Bold   | confident, declarative, unbothered swagger |

---

## 9. Hard Rules

1. **A job always produces a video** — degrade gracefully; only fatal if no ffmpeg or zero usable scenes.
2. **Name the person + control the wardrobe** in every image prompt.
3. **Team identity = colors + players + context**, never logos or readable text on clothing.
4. **Consecutive scenes never share a speaker** (until voice pinning is available).
5. **A scene is one continuous take** — camera field must describe a single framing.
6. **Product copy is never generated by the model** — captions, watermark, and AI/parody disclosure are burned in by ffmpeg.
7. **Real likenesses are allowed** under AI/parody disclosure; official team logos remain forbidden.
8. **Review gate is the real defence** — prompt negatives alone are unreliable.

---

## 10. Assembly & Output Spec

Final deliverable: **1080×1920 · 9:16 · H.264/AAC · 30 fps · faststart MP4**

Working directory per run:

```
<work>/
├── input.json
├── plan.json
├── scene0_kf1.jpg … 
├── scene0.mp4 …
├── scene0_n.mp4 …          # normalised
├── joined.mp4
├── poster.jpg
├── assets.json
└── result.json
```

Assembly steps:
1. Scale/crop to 1080×1920
2. Loudness-normalise each clip to –16 LUFS
3. Concatenate on hard cuts
4. Burn animated captions
5. Burn permanent AI/parody disclosure
6. Optionally burn product watermark
7. Encode faststart

---

## 11. Cost & Latency Targets

| Duration | Scenes | Images + review | Animation | Total (approx) |
|----------|--------|-----------------|-----------|----------------|
| 15 s     | 2      | ~$0.15          | $2.24     | **~$2.40**     |
| 30 s     | 4      | ~$0.30          | $4.48     | **~$4.80**     |
| 60 s     | 8      | ~$0.60          | $8.96     | **~$9.60**     |

Add ~25% for keyframe retries.  
Hard ceiling: `MAX_JOB_COST_USD` (default 8.0) → degrade rather than exceed.

Without animation (keyframes + Ken Burns): ~$0.35 for a 30 s video — useful for script iteration.

---

## 12. Configuration

```env
PIPELINE_MODE=real
OPENAI_API_KEY=...
OPENAI_PLAN_MODEL=gpt-4o-mini
OPENROUTER_API_KEY=...
IMAGE_PROVIDER=openrouter
IMAGE_MODEL=x-ai/grok-imagine-image-quality
VIDEO_PROVIDER=openrouter
VIDEO_MODEL=x-ai/grok-imagine-video-1.5
VIDEO_RESOLUTION=720p
MAX_JOB_COST_USD=8.0
```

---

## 13. Quality Checklist

A video is high-quality when:

- [ ] Faces are recognisable as the intended real athletes
- [ ] Team takes use correct players + color palette
- [ ] No readable text, official logos, or crests appear
- [ ] No collages or multi-panel frames
- [ ] No severe anatomy defects
- [ ] Each scene is a single continuous take
- [ ] Dialogue is clear and matches the planned line (within normal ad-lib)
- [ ] Audio is loudness-normalised with ambient crowd under dialogue
- [ ] Captions and AI/parody disclosure are present and legible
- [ ] Final file is exactly 1080×1920, 30 fps, H.264/AAC, faststart
- [ ] User’s original take is preserved and escalated, never reversed

---

## 14. Implementation Order

1. Character catalog + AI reference image generation
2. Team palette table + focus detection
3. Planner + repair layer (add team-aware instructions)
4. Keyframe generation + vision review gate
5. Video generation conditioned on approved keyframes
6. Assembly pipeline (ffmpeg) with captions + disclosure
7. Cost ceiling + degradation paths
8. Parallel scene generation
9. Durable job queue + provenance tables
10. Continuous measurement of cost, latency, and publish rate

---

## 15. Catalog Management Summary

| Task                         | How |
|------------------------------|-----|
| Add a player                 | Write look description → generate 2–3 AI reference stills → add JSON entry → link to team(s) |
| Add a team                   | Add colors, jersey_description, venues, associated player IDs |
| Choose references at runtime | Direct lookup by character ID from the plan |
| Update references            | Regenerate only when image model quality jumps significantly |
| Keep catalog size            | Small and curated (quality over quantity) |

---