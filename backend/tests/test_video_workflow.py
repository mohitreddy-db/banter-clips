"""Workflow robustness tests.

The pipeline's contract is that it never refuses to produce a video, so most
of these feed it something broken and assert it still yields a valid plan.

Runs under pytest, or standalone:
    .venv/bin/python tests/test_video_workflow.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.video import catalog, defaults, focus, library, media, planner, prompts  # noqa: E402
from app.video import enhancer, prompt_registry, providers, review, shotwriter  # noqa: E402
from app.video.types import CastMember, Scene, VideoPlan  # noqa: E402


# ------------------------------------------------------------ input resolution

def test_resolve_accepts_nothing():
    r = defaults.resolve()
    assert len(r.take) >= defaults.MIN_TAKE_CHARS
    assert r.sport in defaults.SPORTS
    assert r.tone in defaults.TONES
    assert r.scene_count >= defaults.MIN_SCENES


def test_resolve_rejects_junk_without_failing():
    r = defaults.resolve("Messi is finished", sport="quidditch", tone="SPICY", seconds="abc")
    assert r.sport == "Soccer"      # inferred from the take, not the bad input
    assert r.tone == defaults.DEFAULT_TONE
    assert r.seconds == defaults.DEFAULT_SECONDS


def test_reference_person_is_cast_by_the_planner_and_bound_in_the_keyframe():
    """The user's uploaded photo must flow all the way through: resolve
    carries the flag, the planner is told to cast id='reference' without
    describing the face, and the keyframe prompt names the photo as that
    member's identity. Before this, the model drew a generic stand-in."""
    r = defaults.resolve("A take about the person in the reference photo.",
                         "NBA", "Funny", 15, has_reference=True)
    assert r.has_reference is True
    assert defaults.resolve("Plain take with no photo attached here.").has_reference is False

    told = prompts.planner_user_message("t", "NBA", "Funny", [], [], has_reference=True)
    assert "id='reference'" in told
    assert "never their face" in told.lower()
    assert "id='reference'" not in prompts.planner_user_message("t", "NBA", "Funny", [], [])

    member = CastMember(id="reference", name="a Philly die-hard",
                        look="", wardrobe="courtside casual", voice="")
    line = prompts.reference_binding(member)
    assert "first attached image" in line.lower()
    assert "a Philly die-hard" in line and "EXACTLY" in line


def test_identity_route_exists_only_with_a_real_provider_and_model():
    """Reference scenes render on a chat-shaped identity model (Grok ignores
    attached faces). Stub mode and an empty model both disable the route so
    development and the standard pipeline never touch it."""
    from app.config import settings

    old = (settings.IMAGE_PROVIDER, settings.OPENROUTER_API_KEY,
           settings.IMAGE_IDENTITY_MODEL)
    try:
        settings.IMAGE_PROVIDER = "openrouter"
        settings.OPENROUTER_API_KEY = "test-key"
        settings.IMAGE_IDENTITY_MODEL = "google/gemini-2.5-flash-image"
        p = providers.identity_image_provider()
        assert isinstance(p, providers.ChatImageProvider) and p.available

        settings.IMAGE_IDENTITY_MODEL = ""
        assert providers.identity_image_provider() is None

        settings.IMAGE_IDENTITY_MODEL = "google/gemini-2.5-flash-image"
        settings.IMAGE_PROVIDER = "stub"
        assert providers.identity_image_provider() is None
    finally:
        (settings.IMAGE_PROVIDER, settings.OPENROUTER_API_KEY,
         settings.IMAGE_IDENTITY_MODEL) = old


def test_fit_frame_covers_any_canvas_to_the_916_frame():
    """Chat image models pick their own canvas; the animator needs 720x1280
    exactly, cover-cropped rather than stretched or letterboxed."""
    if not media.available():
        return
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "wide.jpg"
        media._run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=640x480",
                    "-frames:v", "1", str(src)], "test frame")
        out = media.fit_frame(src, Path(td) / "fit.jpg")
        assert out is not None
        info = media.probe(out)
        assert (info["width"], info["height"]) == (720, 1280)


def test_resolve_infers_sport_per_league():
    assert defaults.resolve("Wemby can't find Brunson").sport == "NBA"
    assert defaults.resolve("that quarterback threw a pick six").sport == "NFL"
    assert defaults.resolve("a bullpen that blows every home run lead").sport == "MLB"


def test_resolve_replaces_a_too_short_take():
    assert defaults.resolve("no").take == defaults.GENERIC_TAKE
    assert defaults.resolve("   ").take == defaults.GENERIC_TAKE


def test_resolve_clamps_duration_and_scales_scenes():
    assert defaults.resolve("x" * 20, seconds=-5).seconds == defaults.DEFAULT_SECONDS
    assert defaults.resolve("x" * 20, seconds=9999).scene_count <= defaults.MAX_SCENES
    assert defaults.resolve("x" * 20, seconds=30).scene_count > \
           defaults.resolve("x" * 20, seconds=15).scene_count


def test_resolve_truncates_an_overlong_take():
    assert len(defaults.resolve("x" * 5000).take) <= 280


def test_guided_direction_reaches_the_planner_prompt():
    resolved = defaults.resolve("Messi is still the GOAT", direction="A tense press room")
    message = prompts.planner_user_message(
        resolved.take, resolved.sport, resolved.tone, [], [], direction=resolved.direction
    )
    assert "A tense press room" in message


def test_seedance_capabilities_keep_audio_and_valid_bounds():
    mini = providers.video_options("bytedance/seedance-2.0-mini", 2, "1080p")
    assert mini == {"duration": 4, "resolution": "720p", "generate_audio": True}
    pro = providers.video_options("bytedance/seedance-1-5-pro", 20, "1080p")
    assert pro["duration"] == 12 and pro["generate_audio"] is True
    assert providers.video_options("another/provider", 2, "1080p") == {
        "duration": 2, "resolution": "1080p"
    }


# --------------------------------------------------------------------- library

def test_roster_lookup_is_fuzzy_and_total():
    assert library.resolve_member("Wemby", "NBA").id == "wembanyama"
    assert library.resolve_member("victor wembanyama", "NBA").id == "wembanyama"
    # Off-roster names still yield a renderable member rather than None.
    stranger = library.resolve_member("Some Unknown Player", "NBA")
    assert stranger.name and stranger.look and stranger.wardrobe


def test_every_sport_has_a_roster_and_venues():
    for sport in defaults.SPORTS:
        assert library.roster_for(sport)
        assert library.venues_for(sport)


# --------------------------------------------------------------------- planner

def _plan(**kw) -> VideoPlan:
    return planner.build_plan(defaults.resolve(**kw), client=None)


def test_plan_without_a_model_is_still_complete():
    plan = _plan(take="Seven foot four and he still can't find Brunson", seconds=15)
    assert plan.source == "fallback"
    assert len(plan.scenes) == 4          # shot-list structure: anchor + cutaways
    assert plan.cast
    assert all(s.action and s.venue for s in plan.scenes)
    assert any(s.line for s in plan.scenes)   # silent cutaways allowed, silent video not
    # ONE WORLD: every shot shares the same venue text verbatim.
    assert len({s.venue for s in plan.scenes}) == 1


def test_scene_count_follows_duration():
    """Shot-list structure (VIDEO-REALISM-PLAN): anchor + short cutaways."""
    assert len(_plan(take="x" * 20, seconds=10).scenes) == 3
    assert len(_plan(take="x" * 20, seconds=15).scenes) == 4
    assert len(_plan(take="x" * 20, seconds=30).scenes) == 7
    # Shot lengths always sum to the requested duration (within rounding).
    for secs in (10, 15, 30):
        total = _plan(take="x" * 20, seconds=secs).total_seconds
        assert abs(total - secs) < 1.0, (secs, total)


def test_beats_are_hook_then_escalation_then_payoff():
    scenes = _plan(take="x" * 20, seconds=60).scenes
    assert scenes[0].beat == "hook"
    assert scenes[-1].beat == "payoff"
    assert all(s.beat == "escalation" for s in scenes[1:-1])


def test_consecutive_scenes_never_share_a_speaker():
    """The workaround for cross-clip voice drift — enforced, not advisory."""
    for seconds in (15, 30, 60, 90):
        scenes = _plan(take="Wemby can't find Brunson", seconds=seconds).scenes
        speakers = [s.speaker_id for s in scenes]
        assert all(a != b for a, b in zip(speakers, speakers[1:])), speakers


def test_every_speaker_exists_in_the_cast():
    plan = _plan(take="x" * 20, seconds=60)
    ids = {m.id for m in plan.cast}
    assert all(s.speaker_id in ids for s in plan.scenes)
    assert all(plan.speaker_for(s) is not None for s in plan.scenes)


def test_repair_fills_a_half_empty_model_response():
    """A nearly-right plan is repaired, not rejected."""
    inp = defaults.resolve("Wemby can't find Brunson", seconds=30)
    roster = library.roster_for(inp.sport)
    raw = {"title": "", "scenes": [{"action": "he shrugs"}, {}]}  # 2 of 4, mostly blank
    plan = planner._repair(planner._from_raw(raw, inp, roster), inp, roster,
                           library.venues_for(inp.sport))
    assert len(plan.scenes) == inp.scene_count
    assert all(s.venue and s.camera for s in plan.scenes)
    assert any(s.line for s in plan.scenes)


def test_planner_survives_garbage_from_the_model():
    inp = defaults.resolve("x" * 20)
    roster = library.roster_for(inp.sport)
    for raw in ({}, {"scenes": "not a list"}, {"cast": [None, 5], "scenes": [1, 2]}):
        plan = planner._repair(planner._from_raw(raw, inp, roster), inp, roster,
                               library.venues_for(inp.sport))
        assert len(plan.scenes) == inp.scene_count
        assert plan.cast


def test_json_parsing_handles_fences_and_prose():
    assert planner._loads('```json\n{"a": 1}\n```') == {"a": 1}
    assert planner._loads('Sure! {"a": 1} hope that helps') == {"a": 1}
    assert planner._loads("not json at all") is None
    assert planner._loads(None) is None


def test_lines_fit_inside_their_scene():
    for seconds in (15, 30, 60):
        for scene in _plan(take="x" * 20, seconds=seconds).scenes:
            assert scene.fits_line(), (scene.seconds, scene.line)


def test_overlong_lines_are_trimmed():
    scene = Scene(seconds=4.0, line=" ".join(["word"] * 60))
    assert not scene.fits_line()
    trimmed = Scene(seconds=4.0, line=scene.trimmed_line())
    assert trimmed.fits_line()


# --------------------------------------------------------------------- prompts

def test_prompts_name_the_subject_and_ask_for_the_real_kit():
    """The name holds the likeness; the authentic kit is what makes the frame
    look like footage instead of a render."""
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    image = prompts.build_image_prompt(plan, plan.scenes[0])
    assert "Wembanyama" in image
    assert "legible" in image
    assert "no lettering" not in image


def test_motion_prompt_carries_the_spoken_line():
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    scene = plan.scenes[0]
    assert scene.line in prompts.build_motion_prompt(plan, scene)


def test_prompts_never_crash_on_an_empty_plan():
    empty = VideoPlan(cast=[], scenes=[Scene()])
    assert prompts.build_image_prompt(empty, empty.scenes[0])
    assert prompts.build_motion_prompt(empty, empty.scenes[0])


# --------------------------------------------------------------------- catalog

def test_catalog_loads_characters_and_teams():
    chars, teams = catalog.characters(), catalog.teams()
    assert "wembanyama" in chars and "messi" in chars
    assert "spurs" in teams and "lakers" in teams
    # Every team's associated players actually exist.
    for team in teams.values():
        for pid in team.associated_players:
            assert pid in chars, f"{team.id} references unknown player {pid}"


def test_every_kit_asks_for_legible_lettering():
    """Measured: asking for the real kit renders clean text; banning text
    renders gibberish. Every kit string must ask, not forbid."""
    for team in catalog.teams().values():
        w = team.wardrobe()
        assert "legible" in w, (team.id, w)
        assert "no lettering" not in w, team.id
    for char in catalog.characters().values():
        assert "no lettering" not in (char.default_wardrobe or "")


def test_catalog_reference_selection_never_fails():
    assert catalog.select_references(None) == []
    # A character with no stills yields none rather than raising.
    assert catalog.select_references(catalog.get_character("jokic")) == []
    built = catalog.get_character("wembanyama")
    refs = catalog.select_references(built, "tight close-up on his face")
    assert len(refs) <= 2 and all(p.exists() for p in refs)


# ----------------------------------------------------------------------- focus

def test_focus_detects_player_team_matchup_generic():
    assert focus.detect("Wemby is overrated", "NBA").kind == "player"
    assert focus.detect("The Lakers are frauds", "NBA").kind == "team"
    assert focus.detect("Lakers vs Warriors tonight", "NBA").kind == "matchup"
    assert focus.detect("Refs are terrible this year", "NBA").kind == "generic"


def test_player_focus_inherits_their_team():
    """'Wemby is overrated' should still render in Spurs black and silver."""
    f = focus.detect("Wemby is overrated", "NBA")
    assert "wembanyama" in f.player_ids
    assert "spurs" in f.team_ids


def test_team_take_dresses_the_cast_in_team_colours():
    plan = _plan(take="The Lakers are complete frauds this season", sport="NBA")
    lebron = next((m for m in plan.cast if m.id == "lebron"), None)
    assert plan.focus == "team" and "lakers" in plan.team_ids
    if lebron:
        assert "purple" in lebron.wardrobe and "legible" in lebron.wardrobe


def test_focused_player_leads_the_roster_and_venue_is_on_brand():
    r = defaults.resolve("Wemby is overrated and everyone knows it")
    assert r.focus.kind == "player"
    plan = planner.build_plan(r, client=None)
    assert any(m.id == "wembanyama" for m in plan.cast)
    # Team venue context flows into the resolved default venue.
    assert "black and silver" in r.venue or "silver" in r.venue


def test_catalog_mention_settles_the_sport():
    assert defaults.resolve("Ohtani is from another planet").sport == "MLB"
    assert defaults.resolve("Mahomes cannot keep doing this").sport == "NFL"


# -------------------------------------------------------------------- duration

def test_seconds_snap_to_product_tiers():
    """The tiers must match the UI and ClipCreate, or a user gets a length
    they did not pick."""
    for raw, expect in ((10, 10), (15, 15), (30, 30),
                        (11, 10), (20, 15), (26, 30), (9999, 30)):
        assert defaults.resolve("x" * 20, seconds=raw).seconds == expect, raw


def test_every_tier_yields_speakable_scenes():
    for tier in defaults.DURATIONS:
        plan = _plan(take="The Lakers are frauds and everyone knows it", seconds=tier)
        assert abs(plan.total_seconds - tier) < 0.5, tier
        for scene in plan.scenes:
            assert scene.seconds >= 2, (tier, scene.seconds)
            assert scene.fits_line(), (tier, scene.line)


# -------------------------------------------------------------------- captions

def test_caption_wrapping_and_filters():
    lines = media._wrap("a caption long enough to need wrapping onto two lines", 24)
    assert len(lines) >= 2 and all(len(l) <= 30 for l in lines)
    # Captions burn as timed word-chunks that tile the scene's window: the
    # first chunk starts at the window start, the last ends at the window end.
    filters = media.caption_filters([(0.0, 3.5, "he said what he said")], "/font.ttf")
    assert filters and "between(t,0.00," in filters[0]
    assert filters[-1].split("between(t,")[1].startswith(tuple("0123456789"))
    assert ",3.50)" in filters[-1]
    # Newlines never reach drawtext — they render literally as "n" (measured).
    assert not any("\n" in f for f in filters)


def test_captions_never_drop_words():
    """The block style silently truncated at 2 lines x 24 chars — every clip
    reviewed on 2026-08-20 shipped a punchline cut mid-sentence."""
    line = ("Jordan might have the killer instinct but I am bringing the "
            "power that breaks dynasties tonight and every night after")
    filters = media.caption_filters([(0.0, 10.0, line)], "/font.ttf")
    texts = [Path(f.split("textfile=")[1].split(":")[0]).read_text() for f in filters]
    assert " ".join(" ".join(texts).split()) == line


def test_caption_chunks_merge_rather_than_flash():
    # A long line in a tiny window widens chunks instead of flashing them.
    chunks = media.caption_chunks("one two three four five six seven eight", 1.5)
    assert all(t1 - t0 >= media.CAPTION_MIN_CHUNK_SECONDS or len(chunks) == 1
               for t0, t1, _ in chunks)
    assert " ".join(c for _, _, c in chunks) == "one two three four five six seven eight"


def test_caption_text_goes_through_a_file_not_the_filtergraph():
    """An apostrophe once terminated the quoted string and broke the graph."""
    nasty = "He's got 100%, right: no — see \\this\\"
    filters = media.caption_filters([(0.0, 3.0, nasty)], "/font.ttf")
    assert filters
    for f in filters:
        assert "textfile=" in f and ":text=" not in f   # never inline text
        assert "'" not in f.split(":enable")[0]         # no raw quotes in the graph
    written = Path(filters[0].split("textfile=")[1].split(":")[0]).read_text()
    assert written and written in nasty             # verbatim, unescaped


def test_branding_survives_apostrophes_end_to_end():
    """Real ffmpeg, real caption text — the exact string that broke a run."""
    if not media.available():
        return
    scratch = Path(tempfile.mkdtemp(prefix="banter_test_"))
    try:
        source = scratch / "in.mp4"
        media._run([
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi",
            "-i", f"color=c=black:s=270x480:d=2:r=15",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-shortest", "-c:v", "libx264", "-c:a", "aac", str(source),
        ], "test fixture")
        out = media.brand(
            source, scratch / "out.mp4", "AI-generated parody", "BanterClips",
            captions=[(0.1, 1.9, "He's run out of things to throw: 100%")],
        )
        assert media.probe(out).get("duration", 0) > 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


# ------------------------------------------------------------ photorealism

def test_model_style_can_never_replace_the_photoreal_anchor():
    """The bug that made one scene a cartoon: style REPLACED the bible."""
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    plan.style = "harsh spotlights, metallic silver-blue grade"
    image = prompts.build_image_prompt(plan, plan.scenes[0])
    motion = prompts.build_motion_prompt(plan, plan.scenes[0])
    for text in (image, motion):
        assert "REAL PHOTOGRAPH" in text
        assert "photoreal" in text.lower()
        assert "Never animation, illustration, cartoon" in text
        assert "metallic silver-blue grade" in text   # flavour still survives


def test_medium_words_are_stripped_from_model_style():
    assert "cartoon" not in prompts.safe_style("moody grade, cartoon shading").lower()
    assert "3D render" not in prompts.safe_style("warm light, 3D render")
    assert "warm light" in prompts.safe_style("warm light, 3D render")
    assert prompts.safe_style("") == ""


def test_review_hard_fails_a_non_photoreal_frame():
    class FakeVision:
        available = True

        def complete_json(self, *_a, **_k):
            return ('{"readable_text":"NONE","has_text_defect":false,'
                    '"has_real_logo":false,"subject_matches":true,'
                    '"is_single_frame":true,"is_photoreal":false,'
                    '"medium":"cartoon","minor_defects":"NONE",'
                    '"severe_defects":"NONE","lower_quarter_clean":true}')

    verdict = review.review_keyframe(Path(__file__), "Messi", FakeVision())
    assert not verdict
    assert any("photoreal" in h for h in verdict.hard)


# ------------------------------------------------------------- text props

def test_props_may_carry_text_and_the_planner_states_it():
    """Blanking props was part of the same mistake: a scoreboard with no
    numbers is not a scoreboard, and asking for one produced gibberish."""
    assert "Props may carry writing" in prompts.PLANNER_SYSTEM
    assert "block capitals" in prompts.PLANNER_SYSTEM
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    plan.scenes[0].action = "he reads a newspaper on the bench"
    image = prompts.build_image_prompt(plan, plan.scenes[0])
    assert "completely blank" not in image


def test_planner_still_demands_live_action():
    """The photoreal rule survives the text-ban removal — they were separate
    defences and only the text one was wrong."""
    assert "LIVE ACTION" in prompts.PLANNER_SYSTEM


# ---------------------------------------------------------------- framing

def test_image_prompt_asks_for_whole_bodies_not_a_calm_lower_quarter():
    """"Keep the lower quarter calm" made the model cut legs at mid-thigh."""
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    image = prompts.build_image_prompt(plan, plan.scenes[0])
    assert "heads and feet included" in image
    assert "lower quarter" not in image
    assert "cropped at the knees" in image


def test_planner_prefers_full_figure_framings():
    assert "Prefer wide and full" in prompts.PLANNER_SYSTEM
    assert "9:16 frame and physical" in prompts.PLANNER_SYSTEM


def test_camera_is_four_separate_axes():
    """One free-text camera field made the model guess which axis we meant,
    and invited shot lists — which render as split screens."""
    scene = Scene(shot_size="wide shot", camera_angle="low angle",
                  camera_move="slow push-in", lens="24mm")
    block = prompts._camera_block(scene)
    for axis in ("wide shot", "low angle", "slow push-in", "24mm"):
        assert axis in block
    # A still freezes the camera even when the scene specifies a move.
    assert "push-in" not in prompts._camera_block(scene, single=True)
    assert "locked-off" in prompts._camera_block(scene, single=True)


def test_motion_prompt_covers_every_directed_field():
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    scene = plan.scenes[0]
    scene.beats = "he freezes for a beat, then the pile topples"
    scene.expression = "eyebrows raised a millimetre"
    scene.blocking = "coach seated left, Wemby standing right"
    scene.lighting = "hard overhead floodlights"
    scene.sfx = "sneakers squeaking"
    scene.transition = "he turns away from camera"
    text = prompts.build_motion_prompt(plan, scene)
    for label in ("Camera:", "Subject:", "Action:", "Blocking:", "Timing:",
                  "Expression:", "Setting:", "Lighting:", "Ambient:",
                  "Style:", "Ends on:"):
        assert label in text, label
    assert "No music" in text
    # We burn our own captions; a second set from the model would collide.
    assert "No subtitles" in text


def test_only_the_speaker_lip_syncs():
    """Two clips shipped with two people mouthing one line in identical sync
    (2026-08-28). Naming the speaker was not enough — everyone else has to be
    told to stay shut, and a silent shot has to say nobody speaks at all."""
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    spoken = [s for s in plan.scenes if s.line]
    assert spoken, "need a scene with dialogue"
    for scene in spoken:
        text = prompts.build_motion_prompt(plan, scene)
        speaker = plan.speaker_for(scene)
        assert f"Only {speaker.name}'s lips move in sync" in text
        assert "Nobody else speaks, mouths or echoes it" in text
        assert "One voice on the track." in text
        # Last word wins: a shot description can itself put several mouths in
        # motion ("both mouths agape"), so this has to sit at the very end.
        assert text.rstrip().endswith("One voice on the track.")
    for scene in (s for s in plan.scenes if not s.line):
        assert "nobody speaks and no lips move" in prompts.build_motion_prompt(plan, scene)


def test_nobody_is_rendered_twice():
    """A person drawn twice is the most obviously-broken defect a viewer sees,
    so every prompt forbids it and the review gate fails the frame."""
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    for scene in plan.scenes:
        for text in (prompts.build_image_prompt(plan, scene),
                     prompts.build_motion_prompt(plan, scene)):
            assert "EXACTLY ONCE" in text
            assert "twin" in text

    class Doubled:
        available = True

        def complete_json(self, *_a, **_k):
            return json.dumps({"duplicate_person": True, "is_photoreal": True,
                               "is_single_frame": True})

    with tempfile.TemporaryDirectory() as tmp:
        frame = Path(tmp) / "f.jpg"
        frame.write_bytes(b"x")
        verdict = review.review_keyframe(frame, "Wemby", Doubled())
    assert not verdict, "a duplicated person must be a hard failure"
    assert any("twice" in h for h in verdict.hard)
    # And the retry says what to fix, rather than just trying again.
    assert "exactly ONE time" in prompts.escalate("p", verdict.hard)


def test_the_expected_real_logo_is_not_reported_as_a_problem():
    """Real crests and sponsor boards are what make a frame read as broadcast
    footage — noting them filled every clip's provenance with a warning about
    the thing we asked for."""
    class Logos:
        available = True

        def complete_json(self, *_a, **_k):
            return json.dumps({"has_real_logo": True, "is_photoreal": True,
                               "is_single_frame": True, "visible_text": "REAL MADRID"})

    with tempfile.TemporaryDirectory() as tmp:
        frame = Path(tmp) / "f.jpg"
        frame.write_bytes(b"x")
        verdict = review.review_keyframe(frame, "Mourinho", Logos())
    assert verdict, "real logos are expected, never a failure"
    assert not any("logo" in note.lower() for note in verdict.soft + verdict.hard)


def test_the_shot_is_anchored_to_whoever_it_is_actually_about():
    """A silent shot's speaker_id is a leftover field. One clip's action was
    entirely about a forward while speaker_id named the manager, so the
    keyframe was anchored to the wrong face and the model drew both."""
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    scene = plan.scenes[-1]
    forward, manager = plan.cast[0], plan.cast[-1]
    scene.line = ""
    scene.speaker_id = manager.id
    scene.action = f"{forward.name} spins away laughing, alone in frame"
    assert prompts.visible_cast(plan, scene)[0] is forward
    assert prompts.cast_clause(plan, scene).startswith(forward.name)


def test_a_person_is_described_by_something_that_describes_them():
    """`short_look` attributes dialogue. It used to emit pure modifiers —
    "Wembanyama, an extremely tall, says" — which describe nobody."""
    for member in _plan(take="Wemby can't find Brunson", seconds=15).cast:
        look = prompts.short_look(member)
        assert len(look.split()) >= 3
        assert not look.split()[-1].rstrip(",.;").lower() in {
            "a", "an", "the", "very", "extremely", "tall", "fast", "with"
        }, look


def test_out_of_provider_credits_pauses_instead_of_shipping_stills():
    """The failure that shipped twice: the provider ran dry, every scene
    degraded to a gradient placeholder, and the 'successful' slideshow charged
    the user. Now the job pauses, completed scenes are reused from the
    checkpoint, and nothing pretends to be a video."""
    import subprocess
    from app.video import providers, runner

    class Broke:
        available = True

        def generate(self, *_a, **_k):
            raise providers.OutOfCredits("no money")

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        work.mkdir()
        # Scene 0 finished on a previous run: a real keyframe and clip exist
        # and the checkpoint records them.
        kf = work / "scene0_kf1.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                        "-i", "color=c=blue:s=72x128", "-frames:v", "1", str(kf)],
                       check=True)
        clip0 = work / "scene0.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                        "-i", "color=c=blue:s=72x128:d=1", "-pix_fmt", "yuv420p",
                        str(clip0)], check=True)
        (work / "checkpoint.json").write_text(json.dumps(
            {"0": {"keyframe": str(kf), "clip": str(clip0)}}))

        real = providers.image_provider
        providers.image_provider = lambda: Broke()
        try:
            result = runner.generate_video(
                "Wemby can't find Brunson", "NBA", "Funny", 15,
                work_dir=work, out_path=work / "final.mp4",
            )
        finally:
            providers.image_provider = real

    assert result.paused, "provider 402 must pause, not degrade"
    assert not result.ok
    assert "provider out of credits" in result.error
    # The checkpointed scene was reused for free; nothing became a placeholder.
    scene0 = next(a for a in result.assets if a.index == 0)
    assert scene0.ok and scene0.cost_usd == 0
    assert any("reused" in n for n in scene0.notes)
    for asset in result.assets:
        assert not (asset.keyframe_path and "placeholder" in asset.keyframe_path)
        for note in asset.notes:
            assert "Ken Burns" not in note and "placeholder" not in note


def test_the_fake_voice_stage_is_gone():
    from app.models import CLIP_STATUSES, GENERATION_STAGES

    assert "creating_voice" not in GENERATION_STAGES
    assert "paused" in CLIP_STATUSES


def test_the_sport_is_inferred_so_picking_one_is_optional():
    """Sport used to be a required choice before you could type. Almost every
    take names its own league, club or player, so the words decide it."""
    from app.video import sports as sports_mod

    for take, expected in (
        ("Mbappé just turned Real Sociedad's defense into cone drills", "Soccer"),
        ("Seven foot four and Wemby still couldn't find Brunson", "NBA"),
        ("Mahomes throws another touchdown and the Chiefs win again", "NFL"),
        ("Verstappen wins another grand prix from pole", "F1"),
        ("Kohli scored a century and the IPL crowd went wild", "Cricket"),
        ("Djokovic won Wimbledon again somehow", "Tennis"),
        ("McDavid is dragging the Oilers to the Stanley Cup", "NHL"),
        ("Canelo knocked him out in the third round", "Boxing"),
    ):
        assert sports_mod.infer(take) == expected, take

    # Nothing to go on: fall back to what the user follows, then to a default.
    assert sports_mod.infer("my neighbour is very loud") is None
    assert sports_mod.resolve(None, "my neighbour is very loud", ["NHL"]) == "NHL"
    assert sports_mod.resolve(None, "my neighbour is very loud", []) == "Soccer"
    # An explicit pick always wins over the guess.
    assert sports_mod.resolve("Golf", "Wemby dunked on everyone", []) == "Golf"


def test_ambiguous_names_follow_the_sports_the_fan_actually_watches():
    from app.video import sports as sports_mod

    assert sports_mod.resolve(None, "The Giants collapsed again", ["MLB"]) == "MLB"
    assert sports_mod.resolve(None, "The Giants collapsed again", ["NFL"]) == "NFL"


def test_every_sport_has_its_own_world():
    """Unlisted sports fell through to the NBA venue list, which staged a
    Formula 1 take in a basketball arena."""
    from app.models import SPORTS
    from app.video.library import default_venue

    seen = set()
    for sport in SPORTS:
        venue = default_venue(sport)
        assert venue and venue not in seen, f"{sport} shares a venue with another sport"
        seen.add(venue)
    assert "pit lane" in default_venue("F1")
    assert "cricket" in default_venue("Cricket")


def test_roast_is_a_tone_the_pipeline_understands():
    from app.models import TONES

    assert "Roast" in TONES
    assert "Roast" in prompts.TONE_DIRECTION
    plan = _plan(take="Arsenal bottled it again", tone="Roast", seconds=15)
    assert plan.tone == "Roast"
    assert "roast" in prompts.style_for(plan).lower()


def test_named_teams_and_players_are_requirements_not_hints():
    """A user who types "put Mbappé in it" gets Mbappé in it."""
    resolved = defaults.resolve(
        take="Two legends argue about who is more clutch", tone="Roast",
        also_sports=["NBA"], subjects=["Patrick Mahomes", "LeBron James"],
    )
    message = prompts.planner_user_message(
        resolved.take, resolved.sport, resolved.tone, [], ["a stadium"],
        also_sports=resolved.also_sports, subjects=resolved.subjects,
    )
    assert "MUST feature: Patrick Mahomes, LeBron James" in message
    # A second sport is offered as crossover, never as a second world.
    crossed = defaults.resolve(take="Wemby tries out for the Chiefs", also_sports=["NFL"])
    if crossed.also_sports:
        assert "may cross" in prompts.planner_user_message(
            crossed.take, crossed.sport, crossed.tone, [], ["a stadium"],
            also_sports=crossed.also_sports,
        )


def test_prompts_stay_inside_the_useful_length_band():
    """Every guide measured says over-long prompts restrict the model:
    OpenAI warns they limit creativity, Runway that Gen-4 wants simplicity."""
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    for scene in plan.scenes:
        for text in (prompts.build_image_prompt(plan, scene),
                     prompts.build_motion_prompt(plan, scene)):
            assert len(text.split()) < 320, len(text.split())


def test_captions_sit_below_the_figure_and_above_the_platform_chrome():
    # Fractions, not pixels: resolution is a per-clip choice now (720p free,
    # 1080p Creator), and the captions must sit in the same place either way.
    for resolution in ("720p", "1080p"):
        size = media.dims(resolution)
        font_size, base_y = media._caption_geometry(size)
        last_line = base_y + media.CAPTION_MAX_LINES * int(font_size * 1.3)
        assert base_y > size[1] * 0.78, resolution      # clear of standing legs
        assert last_line < size[1] * 0.92, resolution   # clear of the IG UI strip


def test_dims_resolves_per_clip_resolutions():
    assert media.dims("720p") == (720, 1280)
    # Grok's "1080p" tier really delivers 1088x1920; targeting 1080 exactly
    # would re-encode every scene for 8 invisible pixels.
    assert media.dims("1080p") == (1088, 1920)
    # Unknown or absent falls back to the deployment default, never crashes.
    assert media.dims(None) == (media.WIDTH, media.HEIGHT)
    assert media.dims("cinema") == (media.WIDTH, media.HEIGHT)


def test_retry_escalation_targets_the_actual_failure():
    base = "a prompt"
    assert "REAL PHOTOGRAPH" in prompts.escalate(base, ["not photoreal: cartoon"])
    assert "correctly spelled" in prompts.escalate(base, ["garbled lettering: RUACIS"]).lower()
    assert "ONE single" in prompts.escalate(base, ["not a single frame: collage"])
    assert prompts.escalate(base, []) != base       # always adds something


# --------------------------------------------------------------- enhancer

def _brief(**kw):
    return enhancer.enhance(client=None, **kw)


def test_enhancer_returns_a_complete_brief_with_no_model_and_no_input():
    brief = _brief()
    assert brief.take and brief.sport and brief.tone and brief.seconds
    assert brief.style_id in enhancer.STYLE_PRESETS
    assert brief.style                       # a real style string, always


def test_enhancer_asks_about_a_vague_take():
    brief = _brief(take="lakers bad")
    ids = {q.id for q in brief.questions}
    assert "take" in ids
    assert all(q.why for q in brief.questions)          # every question justified


def test_a_specific_take_is_not_interrogated_about_itself():
    brief = _brief(take="The Lakers are frauds and everyone in the building knows it",
                   sport="NBA", tone="Savage", seconds=15)
    assert "take" not in {q.id for q in brief.questions}


def test_explicit_inputs_are_never_asked_about_again():
    brief = _brief(take="The Lakers are frauds and everyone knows it by now",
                   sport="NBA", tone="Savage", seconds=30)
    ids = {q.id for q in brief.questions}
    assert "tone" not in ids and "seconds" not in ids


def test_every_question_has_a_usable_default():
    for take in ("", "no", "The Lakers are frauds and everyone knows it"):
        for question in _brief(take=take).questions:
            assert question.default or question.kind == "text"


def test_answers_are_applied_and_stop_being_asked():
    brief = _brief(take="The Lakers are frauds and everyone knows it")
    answered = enhancer.apply_answers(brief, {"style": "gritty", "tone": "Savage"})
    assert answered.style_id == "gritty"
    assert answered.tone == "Savage"
    assert "style" not in {q.id for q in answered.questions}


def test_style_presets_are_all_photographic():
    for preset in enhancer.STYLE_PRESETS.values():
        assert not prompts._MEDIUM_WORDS.search(preset["style"]), preset


def test_brief_converts_to_a_resolved_input():
    brief = _brief(take="The Lakers are frauds and everyone knows it", sport="NBA")
    resolved = enhancer.resolved_from(brief)
    assert resolved.sport == brief.sport
    assert resolved.seconds == brief.seconds
    assert resolved.scene_count >= 2


def test_enhancer_survives_a_broken_model():
    class Broken:
        available = True

        def complete_json(self, *_a, **_k):
            raise RuntimeError("boom")

    brief = enhancer.enhance("The Lakers are frauds", client=Broken())
    assert brief.take and brief.source == "fallback"


def test_enhancer_ignores_a_model_that_rewrites_the_take_into_an_essay():
    class Windbag:
        available = True

        def complete_json(self, *_a, **_k):
            return json.dumps({"take": "x " * 400})

    original = "The Lakers are frauds and everyone knows it"
    assert enhancer.enhance(original, client=Windbag()).take == original


# ------------------------------------------------------------- shot writer

def test_a_written_shot_still_gets_every_guardrail():
    """The one time a model was trusted with the rules it dropped "photoreal"
    and a scene rendered as a cartoon. It may describe; it may not delete."""
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    scene = plan.scenes[0]
    scene.shot_prompt = "Wide shot, low angle. He stands very still."
    text = prompts.build_motion_prompt(plan, scene)
    assert scene.shot_prompt.rstrip(".") in text
    assert "REAL PHOTOGRAPH" in text          # anchor survives
    assert "No subtitles" in text             # ours, not the model's
    assert "No music" in text
    assert scene.line in text                 # dialogue is still appended
    # The template's labelled blocks are NOT duplicated on top of the prose.
    assert "Timing:" not in text and "Setting:" not in text


def test_without_a_written_shot_the_template_still_runs():
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    scene = plan.scenes[0]
    assert scene.shot_prompt == ""
    text = prompts.build_motion_prompt(plan, scene)
    assert "Camera:" in text and "Setting:" in text


def test_shot_writer_degrades_to_the_template():
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    assert shotwriter.write(plan, client=None) == {}

    class Broken:
        available = True

        def complete_json(self, *a, **k):
            raise RuntimeError("boom")

    assert shotwriter.write(plan, client=Broken()) == {}


def test_shot_writer_ignores_shots_it_invented():
    """A body for a scene index that does not exist must not be applied."""
    plan = _plan(take="Wemby can't find Brunson", seconds=15)

    class Fake:
        available = True

        def complete_json(self, *a, **k):
            return json.dumps({"shots": [
                {"index": 0, "prompt": "A real shot."},
                {"index": 99, "prompt": "A shot for a scene that does not exist."},
            ]})

    out = shotwriter.write(plan, client=Fake())
    assert set(out) == {0}


def test_written_bodies_are_capped():
    class Windy:
        available = True

        def complete_json(self, *a, **k):
            return json.dumps({"shots": [{"index": 0, "prompt": "word " * 900}]})

    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    body = shotwriter.write(plan, client=Windy())[0]
    assert len(body.split()) <= shotwriter.MAX_BODY_WORDS


def test_speaker_attribution_cuts_at_a_clause_not_mid_phrase():
    """It must also pick a clause that describes somebody. This asserted
    "an extremely tall" for months — the exact dangling-modifier output the
    function was written to prevent, reached because three words of pure
    qualifier satisfied the old length check."""
    member = CastMember(
        name="Victor Wembanyama",
        look="an extremely tall, very slim 7-foot-4 French basketball player with long limbs")
    short = prompts.short_look(member)
    assert short == "very slim 7-foot-4 French basketball player with long limbs"
    assert not short.endswith(("basketball", ","))


# ------------------------------------------------------------- prompt registry

def test_registry_covers_the_prompts_that_exist():
    keys = {p.key for p in prompt_registry.REGISTRY}
    assert {"planner", "review", "image", "motion",
            "reference_still", "research"} <= keys
    for spec in prompt_registry.REGISTRY:
        assert spec.purpose and spec.text and spec.model and spec.stage


# ----------------------------------------------------------------------- types

def test_cast_member_coerces_anything():
    assert CastMember.from_raw("Kevin Durant").name == "Kevin Durant"
    assert CastMember.from_raw(None, 3).id == "cast_3"
    assert CastMember.from_raw({"name": None}).name == "the player"


def test_scene_clamps_a_silly_duration():
    assert Scene.from_raw({"seconds": 900}, 0, "v").seconds <= 15
    assert Scene.from_raw({"seconds": "abc"}, 0, "v").seconds > 0


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL  {name}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
