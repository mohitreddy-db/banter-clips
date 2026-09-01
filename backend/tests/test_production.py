"""Production-readiness tests: storage, demo markers, housekeeping.

These cover the paths that are silent when they break — a download serving the
wrong file, a deleted clip whose bytes survive, a demo clip reaching a real
Instagram account, a job stuck forever because a deploy interrupted it.

Runs under pytest, or standalone:
    .venv/bin/python tests/test_production.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.routers.clips import reference_matches  # noqa: E402
from app.routers.socials import _clear_credentials  # noqa: E402
from app.services import markers, spend, storage, youtube  # noqa: E402
from app.services.housekeeping import STUCK_AFTER  # noqa: E402


# ------------------------------------------------------------------ markers

def test_mock_marker_is_detected_anywhere_and_any_case():
    assert markers.is_simulated("[mock] the Lakers are frauds")
    assert markers.is_simulated("the Lakers are frauds [MOCK]")
    assert not markers.is_simulated("the Lakers are frauds")
    assert not markers.is_simulated(None)


def test_markers_never_survive_into_the_stored_take():
    """A marker in a published caption would be visible to the audience."""
    for raw in ("[mock] The Lakers are frauds", "The Lakers [fail] are frauds",
                "[MOCK][fail] The Lakers are frauds"):
        cleaned = markers.strip(raw)
        assert "[mock]" not in cleaned.lower()
        assert "[fail]" not in cleaned.lower()
        assert "The Lakers" in cleaned


def test_stripping_still_satisfies_the_database_minimum():
    # clips_take_len requires 10..280 characters; stripping must not go under.
    assert len(markers.strip("[mock]")) >= markers.MIN_TAKE_CHARS
    assert len(markers.strip("[mock] hi")) >= markers.MIN_TAKE_CHARS
    assert len(markers.strip("[mock] " + "x" * 500)) <= 280


def test_stripping_leaves_an_unmarked_take_alone():
    take = "The Lakers are frauds and everyone knows it"
    assert markers.strip(take) == take


def test_youtube_metadata_uses_first_line_as_title_and_clamps_it():
    title, description = youtube.metadata("A" * 120 + "\nFull description", "fallback")
    assert len(title) == 100
    assert description == "Full description"


def test_reference_upload_checks_file_signatures():
    assert reference_matches(b"\xff\xd8\xffphoto", ".jpg")
    assert reference_matches(b"\x00\x00\x00\x18ftypmp42", ".mp4")
    assert not reference_matches(b"not really a video", ".mp4")


def test_social_disconnect_removes_every_credential():
    account = SimpleNamespace(
        access_token="access", refresh_token="refresh",
        platform_user_id="platform-user", token_expires_at="later",
    )
    _clear_credentials(account)
    assert account.access_token is None
    assert account.refresh_token is None
    assert account.platform_user_id is None
    assert account.token_expires_at is None


# ------------------------------------------------------------------ storage

def _local():
    root = Path(tempfile.mkdtemp(prefix="banter_store_"))
    return storage.LocalStorage(root, "http://localhost:8000"), root


def test_put_and_read_back():
    store, root = _local()
    try:
        obj = store.put("users/u1/clips/c1/final.mp4", b"video-bytes", "video/mp4")
        assert obj.bytes == len(b"video-bytes")
        assert store.open(obj.key) == b"video-bytes"
        assert store.local_path(obj.key).exists()
        assert obj.url.endswith("/media/users/u1/clips/c1/final.mp4")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_keys_cannot_escape_the_media_root():
    """A traversing key would write anywhere the process can write."""
    store, root = _local()
    try:
        for bad in ("../../etc/passwd", "users/../../../tmp/x.mp4"):
            try:
                store.put(bad, b"x")
            except ValueError:
                continue
            raise AssertionError(f"escaping key was accepted: {bad}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_deleting_a_clip_removes_every_one_of_its_files():
    """Dropping the row alone would leave the video fetchable forever."""
    store, root = _local()
    try:
        prefix = storage.clip_prefix("u1", "c1")
        for name in ("final.mp4", "poster.jpg", "scene0_keyframe.jpg"):
            store.put(f"{prefix}/{name}", b"x")
        store.put(storage.clip_prefix("u1", "c2") + "/final.mp4", b"keep me")

        assert store.delete_prefix(prefix) == 3
        assert store.open(f"{prefix}/final.mp4") is None
        # A sibling clip is untouched.
        assert store.open(storage.clip_prefix("u1", "c2") + "/final.mp4") == b"keep me"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_tiering_keeps_deliverables_and_expires_working_files():
    assert storage.tier_for("final.mp4") == "deliverable"
    assert storage.tier_for("poster.jpg") == "deliverable"
    assert storage.tier_for("scene0_keyframe.jpg") == "evidence"
    for scratch in ("scene0.mp4", "scene0_n.mp4", "joined.mp4"):
        assert storage.tier_for(scratch) == "scratch", scratch


def test_purge_removes_only_expired_scratch():
    import os
    import time

    store, root = _local()
    try:
        prefix = storage.clip_prefix("u1", "c1")
        store.put(f"{prefix}/final.mp4", b"deliverable")
        store.put(f"{prefix}/scene0.mp4", b"scratch-old")
        store.put(f"{prefix}/scene1.mp4", b"scratch-new")

        old = time.time() - 30 * 86400
        os.utime(store.local_path(f"{prefix}/scene0.mp4"), (old, old))
        os.utime(store.local_path(f"{prefix}/final.mp4"), (old, old))

        assert store.purge_scratch(older_than_days=7) == 1
        assert store.open(f"{prefix}/scene0.mp4") is None   # expired scratch
        assert store.open(f"{prefix}/scene1.mp4") is not None  # fresh scratch
        assert store.open(f"{prefix}/final.mp4") is not None   # never expires
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_backend_falls_back_to_local_when_supabase_is_misconfigured():
    from app.config import settings

    original = (settings.STORAGE_BACKEND, settings.SUPABASE_SERVICE_ROLE_KEY)
    try:
        settings.STORAGE_BACKEND, settings.SUPABASE_SERVICE_ROLE_KEY = "supabase", ""
        storage.reset()
        assert isinstance(storage.get(), storage.LocalStorage)
    finally:
        settings.STORAGE_BACKEND, settings.SUPABASE_SERVICE_ROLE_KEY = original
        storage.reset()


def test_public_cache_window_is_short_enough_for_deletion_to_matter():
    """Supabase has no purge API, so the TTL is how long a deleted video
    stays fetchable at the CDN edge."""
    assert storage.PUBLIC_CACHE_SECONDS <= 600


# ------------------------------------------------------------ spend ceiling

def test_a_ceiling_of_zero_disables_the_check():
    original = settings.MAX_DAILY_SPEND_USD
    try:
        settings.MAX_DAILY_SPEND_USD = 0
        assert spend.ceiling() == 0
    finally:
        settings.MAX_DAILY_SPEND_USD = original


def test_the_ceiling_is_low_enough_to_matter_at_real_prices():
    """A clip costs ~$2.40; a ceiling of hundreds would protect nothing."""
    assert 0 < spend.ceiling() <= 100


def test_over_budget_tells_the_user_their_allowance_is_intact():
    assert "allowance was not used" in spend.OVER_BUDGET_MESSAGE.lower()


# ----------------------------------------------------------- sample delivery

def test_the_simulated_run_serves_a_real_video_file():
    """[mock] should exercise upload and serving, not shortcut past them."""
    sample = Path(settings.SAMPLE_CLIP_PATH)
    if not sample.exists():
        return  # not staged in this checkout; deploy copies it in
    assert sample.stat().st_size > 100_000, "sample looks like a placeholder"


def test_sample_is_delivered_under_the_clips_own_key():
    """A demo clip must live at its own key, so delete and download behave
    exactly as they do for a real clip."""
    import types
    import uuid as _uuid

    store, root = _local()
    try:
        original_backend = storage._backend
        storage._backend = store
        sample = Path(settings.SAMPLE_CLIP_PATH)
        if not sample.exists():
            return
        from app.services import mock_pipeline

        clip = types.SimpleNamespace(id=_uuid.uuid4(), user_id=_uuid.uuid4(),
                                     duration_target=15)
        out = mock_pipeline._deliver_sample(clip)
        assert out.get("video_key", "").endswith("final.mp4")
        assert str(clip.id) in out["video_key"] and str(clip.user_id) in out["video_key"]
        assert store.open(out["video_key"]) == sample.read_bytes()
        # Deleting the clip's prefix removes it, same as a real clip.
        assert store.delete_prefix(storage.clip_prefix(clip.user_id, clip.id)) >= 1
    finally:
        storage._backend = original_backend
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------- captions

def test_captions_always_returns_three_even_with_no_model():
    from app.video import captions as cw

    for take in ("The Lakers are frauds and everyone knows it", "", "x"):
        options = cw.suggest(take, "NBA", "Savage", client=None)
        assert len(options) == cw.SUGGESTION_COUNT, take
        assert all(o.strip() for o in options)


def test_captions_survive_a_broken_model():
    from app.video import captions as cw

    class Broken:
        available = True

        def complete_json(self, *_a, **_k):
            raise RuntimeError("boom")

    assert len(cw.suggest("The Lakers are frauds", "NBA", "Savage", client=Broken())) == 3


def test_captions_parse_a_fenced_or_messy_response():
    from app.video import captions as cw

    class Messy:
        available = True

        def complete_json(self, *_a, **_k):
            return 'Sure! {"captions": ["one", "two", "three"]} hope that helps'

    assert cw.suggest("take", "NBA", "Funny", client=Messy())[:3] == ["one", "two", "three"]


def test_caption_length_is_capped():
    from app.video import captions as cw

    class Windbag:
        available = True

        def complete_json(self, *_a, **_k):
            return json.dumps({"captions": ["x " * 900]})

    assert all(len(c) <= cw.MAX_CAPTION_CHARS
               for c in cw.suggest("take", "NBA", "Funny", client=Windbag()))


# ---------------------------------------------------------------- research

def test_research_builds_a_wardrobe_from_the_most_specific_fact():
    """We now render kit text, so a named kit beats a colour palette and a
    real squad number beats none."""
    from app.config import settings as st
    from app.video import research
    from app.video.types import CastMember

    class Fake:
        def __init__(self, payload):
            self.payload = payload

        def post(self, *a, **k):
            raise AssertionError("should not be called directly")

    original = (st.WEB_RESEARCH, st.OPENAI_API_KEY)
    try:
        st.WEB_RESEARCH, st.OPENAI_API_KEY = "openai", "test-key"
        payloads = [
            ({"found": True, "kit": "pink Inter Miami home shirt with the heron crest",
              "number": "10"}, "pink Inter Miami", "the number 10"),
            ({"found": True, "team_colors": ["navy", "gold"], "number": ""},
             "navy and gold", None),
        ]
        for data, expect_kit, expect_num in payloads:
            research._search = lambda *a, _d=data, **k: _d
            m = CastMember(id="x", name="Someone", wardrobe="old")
            research.enrich_member(m, "Soccer")
            assert expect_kit in m.wardrobe, m.wardrobe
            assert "legible" in m.wardrobe
            if expect_num:
                assert expect_num in m.wardrobe
    finally:
        st.WEB_RESEARCH, st.OPENAI_API_KEY = original


def test_research_never_guesses_a_number():
    """A confidently wrong squad number renders cleanly and is wrong on
    screen, which is worse than none."""
    from app.video import research

    assert "rather than guessing" in research.RESEARCH_PROMPT


def test_verification_reports_rather_than_rewrites():
    """Web results are data, not instructions — a person approves the change."""
    from app.video import catalog_verify

    src = Path(catalog_verify.__file__).read_text()
    assert "write_text" not in src, "verification must not edit the catalog"


# --------------------------------------------------------------- ledger

def test_ledger_charges_are_atomic_under_concurrency():
    """Two workers must not each see room for the last dollar and spend it."""
    import threading as th
    from app.video.runner import _Ledger

    ledger = _Ledger(budget=100.0)
    def charge():
        for _ in range(500):
            ledger.charge(0.01)
    threads = [th.Thread(target=charge) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert abs(ledger.spent - 40.0) < 1e-6, ledger.spent


def test_ledger_reports_exhaustion_at_the_ceiling():
    from app.video.runner import _Ledger

    ledger = _Ledger(budget=1.0)
    assert not ledger.exhausted()
    ledger.charge(0.99)
    assert not ledger.exhausted()
    ledger.charge(0.02)
    assert ledger.exhausted()


def test_parallelism_is_capped():
    """Every worker holds a provider connection and a render pins a core."""
    from app.video import runner

    assert 1 < runner.MAX_PARALLEL_SCENES <= 8


# ------------------------------------------------------------- housekeeping

def test_stuck_threshold_exceeds_the_longest_real_run():
    # 12 scenes is the maximum, animation dominates at ~2 min each.
    assert STUCK_AFTER > timedelta(minutes=24)


def test_a_fresh_job_is_never_considered_stuck():
    now = datetime.now(timezone.utc)
    assert now - timedelta(minutes=5) > now - STUCK_AFTER


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
