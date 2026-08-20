# Video quality review — why the clips feel "AI-random" and what fixes it

2026-08-20. Method: extracted frame sheets + full-res probes from the recent
real production clips, reconstructed the **exact** image/motion prompts each
scene was generated with (from `plan.json` + `prompts.py`), and researched
current prompt craft for Veo 3.1 / Grok Imagine (sources at the end).

The benchmark, per the product goal: a user should press one button and get
something indistinguishable from a *planned human edit* on sports Instagram —
not "a good AI video". Everything below is measured against that bar.

---

## 1. Clip-by-clip: take → prompt → what actually rendered

### A. `18280ae1` — "Messi: Ronaldo's Best Banner" (10s, Soccer/Funny)

**User take (verbatim):** *"Is Messi a very good banner for Ronaldo and our
original goat which is Messi."* — garbled input; the model had to guess the
joke.

**What the motion prompt asked (scene 0, verbatim):**
> Full shot, eye level, slow push-in, 35mm lens with moderate depth of field.
> Cristiano Ronaldo, an athletic muscular forward with short dark hair with
> faded sides, sharp jawline, intense focused eyes, light stubble, Portuguese
> features, wearing the authentic Al-Nassr yellow and blue home shirt with the
> club crest and the player's name and number, crisp legible lettering, stands
> left at midfield. He proudly snaps open a huge pink banner reading 'MESSI:
> #1 RONALDO FAN' facing the camera. For the first second Ronaldo snaps the
> banner open; by three seconds Lionel Messi […] strolls in from frame right,
> stands beside Ronaldo, and gives a slow thumbs-up nod. […] Dialogue:
> Cristiano Ronaldo, an athletic muscular forward with short dark hair with
> faded sides, says, "Of course Messi's the best—at promoting me!" — loud,
> with a grand sweeping gesture at the banner. Audio is diegetic only, under
> the dialogue. No music. REAL PHOTOGRAPH on a real camera […] No subtitles,
> no burned-in dialogue text.

**Rendered:** the *best* of the set. Likenesses strong, authentic KAFD
Al-Nassr and Inter Miami kits, banner text perfectly legible, venue consistent
across both scenes. Still broken: scene 1's composition buries the punchline
(Messi tiny at the top of a ladder, Ronaldo crammed into a corner behind the
banner, bodies cropped — directly violating the prompt's own "whole bodies,
nobody cropped" rule), and the caption sits on top of the watermark.

### B. `86ab5974` — "Arsenal Celebrate Like It's the UCL" (16s, 1080p)

**User take:** *"Create a 15-sec funny soccer roast: Arsenal win the Community
Shield and celebrate like they won the Champions League. Show fans partying
wildly, then cut to a trophy labeled 'Community Shield.' End: 'Arsenal fans,
it's August 😂' with bold captions." Use Arsenal players"*

**What the prompt asked:** Mbappe (in **his catalog white #10 kit**) leaping
on Ronaldo (in **his Al-Nassr yellow/blue #7**) surrounded by "fans in Arsenal
shirts". Scene 1: Ronaldo alone holding the Community Shield plate.

**Rendered — the product's core problems in one clip:**
- The user asked for **Arsenal players**. They got France-kit Mbappe riding
  Al-Nassr-kit Ronaldo inside an Arsenal-shirted crowd. The story is visually
  incoherent — three teams in one frame, and the punchline ("Arsenal fans…
  it's August!") is delivered by a man in an Al-Nassr shirt.
- **Scene-to-scene continuity break:** scene 0's crowd is red (Arsenal),
  scene 1's crowd is yellow (Al-Nassr colours). Different stadium mood,
  different confetti. Reads as two unrelated videos cut together.
- **Caption truncated mid-sentence** on screen: "THIS is what football's all
  about! Best night of" — the third wrapped line is silently dropped.
- 1080p request produced a **1088×1920** file (grok's actual "1080p" size) —
  logged as a dimension warning every time.

### C. `87afb9bc` / `d5ded580` / `66aec853` — Arsenal vs City (16s each)

**User take:** *"Create a 15-sec funny AI soccer parody: Arsenal fans arrive
confident for the Community Shield, then Man City fans reveal a giant 'Relax,
it's City' banner. End with a hilarious twist: 'Who's winning tomorrow? 😂'"*

**Rendered:** banner text ('RELAX, IT'S CITY', 'COMMUNITY SHIELD = OURS')
renders clean and legible — text-on-props is a real strength. But:
- Cast again forced to Mbappe/Ronaldo. The user's story is *fans vs fans*;
  the pipeline has no fan characters it will actually cast, so two
  megastars in wrong kits act out a fan skit — uncanny, not funny.
- **Mbappe's kit mutates between scenes**: white-with-red "MBAPPÉ 10"
  (Arsenal-ish mashup) in scene 0 → PSG-style white/navy in scene 1. He has
  **no reference stills in the catalog**, so his identity is text-only and
  re-rolled per scene.
- Caption truncation again: "Community Shield? This time it's Arsenal's —"
  (dropped clause).
- Same take submitted 3 times ≈ $12 spent chasing a result the pipeline
  cannot deliver — the user was fighting the tool, not the model.

### D. `977bc2e9` — "LeBron vs Curry vs Jordan 3-on-3" (30s, NBA/Bold)

**User take:** *"Create a 30-sec AI basketball debate: 'If Steph Curry, LeBron
James and Michael Jordan played 3-on-3, who wins?' Debate Jordan's killer
instinct, LeBron's power and Curry's shooting, then reveal a surprising
winner. Use dramatic music, bold captions and crowd reactions."*

**Rendered:** individually the LeBron and Curry shots are genuinely good —
authentic Lakers/Warriors kits, arena depth, strong faces. But:
- **Michael Jordan never appears** — he's not in the catalog, so a debate
  *about* Jordan shows an empty Bulls jersey on a chair (with the wrong
  number). The "surprising winner reveal" the user asked for became a
  reporter holding a hand-drawn cardboard sign — the payoff collapses.
- **Gibberish text everywhere the prompt didn't specify text:** jersey
  sponsor "Hobiin", arena boards "ffe far", scoreboard "3:5J 24". Specified
  text renders; unspecified text renders as alien script.
- The final scene is a visibly synthetic collage (reporter pasted between
  jersey-chairs against a flat crowd wall) — the worst frame in the set is
  the *last* thing viewers see.
- Captions truncated in all three scenes ("…but I'm", "…but you can't").
- "Use dramatic music" — ignored by design (prompts force "No music"), and
  nothing tells the user that.

---

## 2. Systemic diagnosis (ranked by damage to perceived quality)

1. **Burned captions truncate mid-sentence — every clip.** `media.py` wraps
   to 24 chars × max 2 lines and silently drops the rest. A viewer can't
   read half a punchline; nothing screams "broken AI tool" louder. This is
   deterministic ffmpeg code — the fix costs nothing per clip.

2. **Casting ignores the story.** The planner may only cast from an
   18-character catalog, and wardrobe is hard-locked to each character's own
   club kit. Any take about a *team* (Arsenal, City), a *fan base*, or an
   off-catalog legend (Jordan) is forcibly rewritten into "Ronaldo and
   Mbappe in their own kits doing something unrelated". The output can be
   photorealistic and still feel random, because it is not the video the
   user asked for. Also: every soccer clip stars the same two faces —
   the feed looks like one joke repeated.

3. **No cross-scene consistency mechanism.** Each scene is an independent
   image→video roll sharing only prompt text (venue string, wardrobe words)
   and, for a few characters, 1–2 catalog stills at the *image* stage only.
   Nothing anchors scene 2 to what scene 1 actually rendered — hence kit
   mutations, crowd-colour flips, crest drift. Characters with empty
   `reference_images` (Curry, Mbappe, Jokic, Mahomes…) have no identity
   anchor at all.

4. **The AI/parody disclosure is not burned in.** `VIDEO_DISCLOSURE` is
   unset in prod, so the "on every plan, every video" label from BRD BR-06
   — the legally load-bearing part of the real-players parody stance —
   currently does not exist. (One line in the droplet .env.)

5. **Unspecified in-frame text becomes gibberish.** Prompted banner text is
   a strength; incidental text (sponsors, scoreboards, ad boards) is a
   liability. The prompts never say what these should be, so the model
   invents lettering.

6. **The take box is being used as a prompt box.** Recent real users typed
   full production briefs ("Create a 15-sec… show fans… then cut to… end
   with… use dramatic music"). The pipeline treats them as an *opinion*,
   partially honours the beats, silently drops explicit instructions (music,
   "use Arsenal players", the requested ending card). The user's mental
   model and the product's contract have diverged — and they burn $4 per
   attempt discovering it.

7. **Weak payoffs.** The last scene is consistently the weakest (composites,
   sign-holding reveals). Comedy structure means the payoff carries the
   share; today it carries the artifacts.

8. **1080p delivers 1088×1920** (grok's actual size). Cosmetic, but it's a
   per-clip warning and non-standard metadata; either crop to 1080 in
   `normalise` or accept 1088 as the 1080p spec.

What is *already good* and worth keeping: the photoreal look and likeness of
catalog characters with reference stills; authentic-kit rendering; prop text;
the shot-grammar vocabulary (framing/lens/lighting per scene); dialogue
attribution format (lip-sync works); per-scene micro-timing.

---

## 3. What good prompting actually looks like (research)

Common ground across Google's official Veo 3.1 guide and Grok Imagine
prompting guides:

- **One shootable moment per prompt**, structured:
  `[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]`.
  Natural sentences, not keyword walls. *Our prompts follow the spirit — but
  bury it under ~40% repeated boilerplate.*
- **Audio as its own layer**: separate sentences for dialogue (quoted),
  SFX (`SFX: net swish`), ambience (`Ambient noise: …`). *We do this —
  keep it.*
- **Timestamps beat adjectives**: `[00:00-00:02] …` / `[00:02-00:04] …`
  for pacing, instead of "for the first second… by three seconds…".
  Veo explicitly supports timestamped multi-beat prompts; Grok guides
  recommend the same precision. *Ours uses prose timing — convert.*
- **Say what you want, not what you don't**: "a desolate landscape with no
  buildings" beats "no man-made structures". *Our prompts carry ~450 chars
  of negations per scene ("Not animation… No split screen… No subtitles…"),
  repeated twice in some prompts.*
- **Short prompts are more stable for motion**: "keep prompts short for
  motion stability — camera + action + ambience" (Grok guidance). *Our
  motion prompts run 900–1,300 chars with the full character description
  repeated 2–3× (once per mention, once inside the Dialogue clause).*
- **Consistency is solved with references, not adjectives**:
  - Veo: "Ingredients to Video" — reference images for each character +
    the *setting*, reused across every shot.
  - Grok Imagine 1.5: **reference-to-video** accepts multiple tagged
    reference images (character/product/environment) — and OpenRouter's
    video API exposes this as `input_references` alongside `frame_images`.
    *We currently send only the single first-frame keyframe; the field that
    would lock identity and venue across scenes goes unused.*
  - First/last-frame chaining: generate the transition by giving scene N's
    last frame as scene N+1's anchor.
- **Known pipeline pattern for consistent multi-shot characters**: generate
  a character sheet once (sharp, evenly lit), reference it in *every*
  scene's generation, and keep prompt description aligned with the
  reference. *Half our catalog has no reference stills at all.*

Also relevant: one of our own prompt-builder bugs surfaced in every clip —
the dialogue clause truncates the speaker's look at the first comma, so
prompts literally say *"Kylian Mbappe, a fast, says, …"*. Junk tokens in
every motion prompt.

---

## 4. Fix plan (ordered: perceived-quality gain ÷ effort)

| # | Fix | Effort | What it buys |
|---|---|---|---|
| 1 | **Captions: never truncate.** Chunk each line into 2–4-word timed groups synced across the scene (word-chunk "karaoke" style — also the native style of real sports reels), auto-shrink font before dropping anything | S | removes the most visible defect from 100% of clips |
| 2 | ~~Burn the disclosure~~ — **dropped by decision 2026-08-20**: the disclosure mandate was removed from the BRD instead; no label is burned | — | — |
| 3 | **Fix `short_look` comma bug**; strip duplicated boilerplate from motion prompts; convert prose timing to `[00:00-00:02]` timestamps; rewrite negations positively | S | cleaner prompts = measurably steadier motion & fewer artifacts, per provider guidance |
| 4 | **Story-first casting**: let the planner (a) restyle wardrobe to the story's team ("an Arsenal red home shirt with white sleeves") instead of hard-locking club kits, (b) cast generic characters (fans, supporters' groups) that exist for exactly these stories, (c) research + synthesize off-catalog names (Jordan) instead of silently dropping them | M | the video the user actually asked for; kills the "same two faces" problem |
| 5 | **Cross-scene anchors**: pass 2–3 `input_references` per animation call — the speaker's catalog stills + scene 0's delivered venue frame; generate reference stills for every active catalog character (one-time, ~$0.10/character) | M | kit/venue/face stability across scenes — the "planned edit" feel |
| 6 | **Name all in-frame text**: prompts should specify scoreboard/ad-board/sponsor text ("courtside boards read BANTER SPORTS") or ask for clean unbranded surfaces — never leave lettering to the model | S | ends gibberish sponsors/scoreboards |
| 7 | **Honour prompt-style takes**: detect briefs ("Create a 15-sec…", "end with…", "use X"), map explicit beats/endings into the plan, and surface what can't be honoured (e.g. music) before spending | M | stops users burning $4/attempt fighting the tool |
| 8 | **Payoff hardening**: final scene gets the strictest review pass + a re-roll budget; prefer physical-comedy payoffs over sign/collage reveals in the planner's beat guidance | S–M | the last frame is the share decision |
| 9 | 1080p: crop/scale 1088→1080 in `normalise` (or declare 1088 the spec) | XS | clean metadata, no warning noise |

Measurement: re-run the same four takes above after each of fixes 1/3/4/5 and
compare against these frame sheets — same-take A/B is the only honest score.

---

## Sources

- [Google Cloud — Ultimate prompting guide for Veo 3.1](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- [GenAIntel — How to prompt Grok Imagine](https://www.genaintel.com/guides/how-to-prompt-grok-imagine)
- [Veo 3 native audio prompt guide (2026)](https://www.veo3ai.io/blog/veo-3-native-audio-prompt-guide-2026)
- [UlazAI — Veo 3 prompting best practices](https://ulazai.com/veo3-prompt-guide/)
- [WaveSpeedAI — Grok Imagine reference-to-video](https://wavespeed.ai/blog/posts/introducing-x-ai-grok-imagine-video-reference-to-video-on-wavespeedai/)
- [Scenario — Grok Imagine Video 1.5 essentials](https://help.scenario.com/articles/5410526625-grok-imagine-video-a-guide-to-ai-motion-creation)
- [OpenRouter — video generation API (`frame_images` / `input_references`)](https://openrouter.ai/docs/features/multimodal/video-generation)
