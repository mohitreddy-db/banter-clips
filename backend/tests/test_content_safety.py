"""Regression coverage for the App Store intimate-contact safety rule."""

import pytest
from fastapi import HTTPException

from app.routers import clips
from app.services import content_safety
from app.video import planner
from app.video.defaults import ResolvedInput
from app.video.types import CastMember, Scene, VideoPlan


@pytest.mark.parametrize(
    "value",
    [
        "The players hug after the final whistle",
        "Show them kissing in the tunnel",
        "They cuddle on the bench",
        "The mascots make out after the win",
        "He wraps his arms around her",
        "A romantic moment between the two stars",
        {"action": "They hold hands on the pitch"},
    ],
)
def test_blocks_intimate_contact_and_common_paraphrases(value):
    assert content_safety.contains_intimate_contact(value)


@pytest.mark.parametrize(
    "value",
    [
        "I love this team's pressing",
        "A contact sport with a hard tackle",
        "The player points to the badge on his shirt",
        "The players celebrate side by side without touching",
        "Messi is still the GOAT.",
    ],
)
def test_allows_normal_sports_language(value):
    assert not content_safety.contains_intimate_contact(value)


def test_router_returns_a_clear_public_error():
    with pytest.raises(HTTPException) as caught:
        clips._require_sports_only("Make the two mascots kiss")
    assert caught.value.status_code == 422
    assert caught.value.detail["code"] == "unsupported_content"
    assert "sports-only" in caught.value.detail["message"]


def test_model_authored_intimate_scene_is_replaced():
    cast = [
        CastMember(id="one", name="Player One"),
        CastMember(id="two", name="Player Two"),
    ]
    plan = VideoPlan(
        take="A normal sports take that is safe.",
        sport="NBA",
        tone="Funny",
        cast=cast,
        scenes=[
            Scene(
                index=0,
                seconds=7.5,
                speaker_id="one",
                action="Player One hugs Player Two after the win",
                blocking="they embrace at centre court",
                line="What a game.",
            ),
            Scene(index=1, seconds=7.5, speaker_id="two", line="Unbelievable."),
        ],
    )
    inp = ResolvedInput(
        take=plan.take,
        sport="NBA",
        tone="Funny",
        seconds=15,
        scene_count=2,
        venue="a basketball arena",
    )

    repaired = planner._repair(plan, inp, cast, [inp.venue])

    assert not content_safety.contains_intimate_contact(repaired.to_dict())
    assert "remain visibly separate" in repaired.scenes[0].blocking
