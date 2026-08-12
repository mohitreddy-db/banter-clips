"""Production-readiness tests: storage, demo markers, housekeeping.

These cover the paths that are silent when they break — a download serving the
wrong file, a deleted clip whose bytes survive, a demo clip reaching a real
Instagram account, a job stuck forever because a deploy interrupted it.

Runs under pytest, or standalone:
    .venv/bin/python tests/test_production.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import markers, storage  # noqa: E402
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
