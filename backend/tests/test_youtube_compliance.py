"""Contract tests for the controls required by YouTube's compliance review."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas import PublishCreate  # noqa: E402
from app.services import housekeeping, youtube  # noqa: E402


def youtube_body(**overrides):
    values = {
        "title": "The creator's exact title",
        "description": "The creator's exact description",
        "privacy_status": "private",
    }
    values.update(overrides)
    return PublishCreate(social_account_id="00000000-0000-0000-0000-000000000001", youtube=values)


@pytest.mark.parametrize("visibility", ["public", "unlisted", "private"])
def test_all_required_visibility_choices_are_accepted(visibility):
    assert youtube_body(privacy_status=visibility).youtube.privacy_status == visibility


def test_unknown_visibility_is_rejected():
    with pytest.raises(ValidationError):
        youtube_body(privacy_status="friends")


def test_title_boundary_and_forbidden_characters():
    assert len(youtube_body(title="x" * 100).youtube.title) == 100
    with pytest.raises(ValidationError):
        youtube_body(title="x" * 101)
    with pytest.raises(ValidationError):
        youtube_body(title="   ")
    with pytest.raises(ValidationError):
        youtube_body(title="Not <allowed>")


def test_description_limit_is_5000_utf8_bytes_not_characters():
    assert youtube_body(description="é" * 2500).youtube.description == "é" * 2500
    with pytest.raises(ValidationError):
        youtube_body(description="é" * 2501)
    with pytest.raises(ValidationError):
        youtube_body(description="Not <allowed>")


def test_upload_sends_exact_creator_values_and_synthetic_disclosure(monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return httpx.Response(
            200,
            headers={"location": "https://upload.youtube.test/session"},
            request=httpx.Request("POST", url),
        )

    def put(url, **kwargs):
        captured["put_url"] = url
        captured["put"] = kwargs
        return httpx.Response(200, json={"id": "video-123"}, request=httpx.Request("PUT", url))

    monkeypatch.setattr(youtube.httpx, "post", post)
    monkeypatch.setattr(youtube.httpx, "put", put)

    video_id = youtube.upload_short(
        "token",
        b"video-bytes",
        title="Exact title",
        description="Exact description 🏀",
        privacy_status="unlisted",
    )

    assert video_id == "video-123"
    assert captured["params"] == {"uploadType": "resumable", "part": "snippet,status"}
    assert captured["json"]["snippet"] == {
        "title": "Exact title",
        "description": "Exact description 🏀",
        "categoryId": "17",
    }
    assert captured["json"]["status"] == {
        "privacyStatus": "unlisted",
        "containsSyntheticMedia": True,
    }
    assert captured["put_url"] == "https://upload.youtube.test/session"
    assert captured["put"]["content"] == b"video-bytes"


class FakeDb:
    def __init__(self):
        self.commits = 0
        self.executed = []

    def execute(self, statement):
        self.executed.append(statement)

    def commit(self):
        self.commits += 1


def test_invalid_grant_immediately_clears_credentials_and_api_data(monkeypatch):
    now = datetime.now(timezone.utc)
    account = SimpleNamespace(
        id="account-id",
        status="connected",
        access_token="access",
        refresh_token="refresh",
        platform_user_id="me",
        token_expires_at=now - timedelta(minutes=1),
        revoked_at=None,
    )
    db = FakeDb()
    response = httpx.Response(
        400,
        json={"error": "invalid_grant"},
        request=httpx.Request("POST", youtube.TOKEN),
    )
    monkeypatch.setattr(youtube.httpx, "post", lambda *args, **kwargs: response)

    youtube.maybe_refresh_token(db, account)

    assert account.status == "revoked"
    assert account.access_token is None
    assert account.refresh_token is None
    assert account.platform_user_id is None
    assert account.token_expires_at is None
    assert account.revoked_at is not None
    assert db.commits == 1
    assert len(db.executed) == 1


def test_expired_connection_without_refresh_token_is_purged():
    account = SimpleNamespace(
        id="account-id",
        status="connected",
        access_token="access",
        refresh_token=None,
        platform_user_id="me",
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        revoked_at=None,
    )
    db = FakeDb()

    youtube.maybe_refresh_token(db, account)

    assert account.status == "revoked"
    assert account.access_token is None
    assert len(db.executed) == 1


class Rows:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class RetentionDb:
    def __init__(self, values):
        self.values = values
        self.commits = 0
        self.closed = False

    def scalars(self, statement):
        return Rows(self.values)

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def test_housekeeping_deletes_youtube_response_link_at_30_days(monkeypatch):
    publish = SimpleNamespace(external_url="https://www.youtube.com/shorts/video-123")
    db = RetentionDb([publish])
    monkeypatch.setattr(housekeeping, "SessionLocal", lambda: db)

    removed = housekeeping.purge_stale_youtube_api_data()

    assert removed == 1
    assert publish.external_url is None
    assert db.commits == 1
    assert db.closed is True
