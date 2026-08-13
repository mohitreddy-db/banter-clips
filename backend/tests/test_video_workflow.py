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
from app.video import enhancer, prompt_registry, review  # noqa: E402
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
    assert len(plan.scenes) == 2
    assert plan.cast
    assert all(s.line and s.action and s.venue for s in plan.scenes)


def test_scene_count_follows_duration():
    assert len(_plan(take="x" * 20, seconds=10).scenes) == 2
    assert len(_plan(take="x" * 20, seconds=15).scenes) == 2
    assert len(_plan(take="x" * 20, seconds=30).scenes) == 4


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
    assert all(s.line and s.venue and s.camera for s in plan.scenes)


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

def test_prompts_name_the_subject_and_forbid_lettering():
    """Both halves matter: the name holds the likeness, the rule kills the text."""
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    image = prompts.build_image_prompt(plan, plan.scenes[0])
    assert "Wembanyama" in image
    assert "no lettering" in image
    assert "no readable text" in image.lower() or "readable text" in image


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


def test_every_wardrobe_forbids_lettering():
    """The no-text rule is load-bearing; every kit string must carry it."""
    for team in catalog.teams().values():
        assert "no lettering" in team.wardrobe()
    for char in catalog.characters().values():
        assert "no lettering" in (char.default_wardrobe or "no lettering")


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
        assert "purple" in lebron.wardrobe and "no lettering" in lebron.wardrobe


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
    filters = media.caption_filters([(0.0, 3.5, "he said what he said")], "/font.ttf")
    assert filters and "between(t,0.00,3.50)" in filters[0]
    # Newlines never reach drawtext — they render literally as "n" (measured).
    assert not any("\n" in f for f in filters)


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
        assert "Not animation, illustration, cartoon" in text
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

def test_text_bearing_props_are_detected_and_blanked():
    props = prompts.text_props_in("Ronaldo scrolls through polls on a tablet", "")
    assert "tablet" in props and "poll" in props
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    plan.scenes[0].action = "he reads a newspaper on the bench"
    image = prompts.build_image_prompt(plan, plan.scenes[0])
    assert "newspaper" in image and "completely blank" in image


def test_planner_is_told_to_avoid_text_props():
    assert "newspaper" in prompts.PLANNER_SYSTEM
    assert "LIVE ACTION" in prompts.PLANNER_SYSTEM


# ---------------------------------------------------------------- framing

def test_image_prompt_asks_for_whole_bodies_not_a_calm_lower_quarter():
    """"Keep the lower quarter calm" made the model cut legs at mid-thigh."""
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    image = prompts.build_image_prompt(plan, plan.scenes[0])
    assert "heads and feet included" in image
    assert "lower quarter" not in image
    assert "nobody cropped at the knees" in image


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


def test_prompts_stay_inside_the_useful_length_band():
    """Every guide measured says over-long prompts restrict the model:
    OpenAI warns they limit creativity, Runway that Gen-4 wants simplicity."""
    plan = _plan(take="Wemby can't find Brunson", seconds=15)
    for scene in plan.scenes:
        for text in (prompts.build_image_prompt(plan, scene),
                     prompts.build_motion_prompt(plan, scene)):
            assert len(text.split()) < 320, len(text.split())


def test_captions_sit_below_the_figure_and_above_the_platform_chrome():
    last_line = media.CAPTION_BASE_Y + media.CAPTION_MAX_LINES * int(
        media.CAPTION_FONT_SIZE * 1.3
    )
    assert media.CAPTION_BASE_Y > media.HEIGHT * 0.78      # clear of standing legs
    assert last_line < media.HEIGHT - 150                  # clear of the IG UI strip


def test_retry_escalation_targets_the_actual_failure():
    base = "a prompt"
    assert "REAL PHOTOGRAPH" in prompts.escalate(base, ["not photoreal: cartoon"])
    assert "blank" in prompts.escalate(base, ["text visible: NIKE"]).lower()
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
