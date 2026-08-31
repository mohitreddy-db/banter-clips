"""External model providers, behind narrow interfaces.

Text (planning and review) goes to OpenAI. Images and video go to OpenRouter.
Each provider has a stub twin that produces something usable offline, so the
pipeline runs end to end with no keys configured at all.

Video generation is deliberately switched off by default (`VIDEO_PROVIDER
= "stub"`). The stub animates the approved keyframe with a slow push-in, which
is the same fallback the pipeline uses when a real animation fails — so
turning generation on later changes cost and polish, not the shape of the run.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path

import httpx

from ..config import settings
from . import media

log = logging.getLogger("banter.video.providers")

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENROUTER = "https://openrouter.ai/api/v1"

# Generous by default. A shot-by-shot plan for twelve scenes, each with camera,
# blocking, expressions, dialogue, lighting and audio, is genuinely long — and
# a response cut off mid-object is unparseable rather than merely brief, so the
# job silently falls back to the deterministic template. Costing a little more
# for headroom is far cheaper than losing the call.
MAX_OUTPUT_TOKENS = 16000


# --------------------------------------------------------------------- text

class TextClient:
    """Chat completion returning JSON. Used for planning and image review."""

    def __init__(self, api_key: str, model: str, timeout: float = 90.0):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def complete_json(
        self, system: str, user: str, image_b64: str | None = None,
        max_tokens: int = MAX_OUTPUT_TOKENS, temperature: float | None = None,
    ) -> str | None:
        """Structured completion. `max_tokens` is deliberately generous.

        A truncated response is not a shorter answer, it is invalid JSON — the
        parse fails and the whole call is wasted, which for the planner means
        silently falling back to the template. Detailed shot descriptions run
        long, so the ceiling is set well above what we expect rather than just
        above it.
        """
        if not self.available:
            return None
        content: object = user
        if image_b64:
            content = [
                {"type": "text", "text": user},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ]
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": content}],
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            body["temperature"] = temperature
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    OPENAI_URL, json=body,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            if resp.status_code >= 400:
                log.warning("text model %s -> %s %s", self.model, resp.status_code, resp.text[:300])
                return None
            return resp.json()["choices"][0]["message"]["content"]
        except Exception:  # noqa: BLE001 — callers fall back
            log.exception("text model call failed")
            return None


class NullTextClient:
    available = False

    def complete_json(self, *_args, **_kwargs) -> None:
        return None


class OutOfCredits(RuntimeError):
    """The provider refused to spend — its account balance is below the
    pre-authorization for the call. Nothing is wrong with the request; money
    is. Callers pause the job (progress saved, user not charged) rather than
    degrading it, because a placeholder video costs the user credits and
    trust while telling them nothing about what actually happened."""


def _raise_if_out_of_credits(resp) -> None:
    if resp.status_code == 402:
        raise OutOfCredits("provider account has insufficient credits")


# ------------------------------------------------------------------- images

class ImageProvider:
    """Keyframe and reference-still generation via OpenRouter's images endpoint.

    The same provider (and therefore the same IMAGE_MODEL) serves both scene
    keyframes and catalog reference stills, so references and keyframes share
    one visual dialect — a deliberate rule from the plan (§5.6).
    """

    def __init__(self, api_key: str, model: str, timeout: float = 180.0):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def generate(
        self, prompt: str, out: Path, references: list[Path] | None = None,
        aspect_ratio: str = "9:16",
    ) -> tuple[Path | None, float]:
        """Returns (path, cost). Path is None if generation failed.

        `references` are catalog stills attached as identity anchors. Support
        for image conditioning varies by model behind OpenRouter, so a request
        the endpoint rejects is retried once without the references — the
        named-subject prompt still carries the likeness on its own (§6).
        """
        if not self.available:
            return None, 0.0
        body: dict = {"model": self.model, "prompt": prompt, "aspect_ratio": aspect_ratio}
        if references:
            # Up to three: two identity stills plus the scene-0 world anchor.
            body["image_urls"] = [_data_uri(p) for p in references if Path(p).exists()][:3]
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{OPENROUTER}/images", json=body,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if resp.status_code >= 400 and references:
                    log.info("image gen with references -> %s; retrying without",
                             resp.status_code)
                    body.pop("image_urls", None)
                    resp = client.post(
                        f"{OPENROUTER}/images", json=body,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
            _raise_if_out_of_credits(resp)
            if resp.status_code >= 400:
                log.warning("image gen -> %s %s", resp.status_code, resp.text[:300])
                return None, 0.0
            data = resp.json()
            payload = (data.get("data") or [{}])[0].get("b64_json")
            if not payload:
                return None, 0.0
            out.write_bytes(base64.b64decode(payload))
            return out, float((data.get("usage") or {}).get("cost") or 0.0)
        except OutOfCredits:
            raise
        except Exception:  # noqa: BLE001
            log.exception("image generation failed")
            return None, 0.0


def _data_uri(path: str | Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()


class StubImageProvider:
    available = True

    def generate(self, prompt: str, out: Path,
                 references: list[Path] | None = None,
                 aspect_ratio: str = "9:16") -> tuple[Path | None, float]:
        try:
            return media.placeholder_image(out), 0.0
        except media.MediaError:
            log.exception("placeholder image failed")
            return None, 0.0


# -------------------------------------------------------------------- video

class VideoProvider:
    """Animation via OpenRouter's async video endpoint.

    Off by default. Enable with VIDEO_PROVIDER=openrouter once you are ready
    to spend — every call here costs real money per second of output.
    """

    def __init__(self, api_key: str, model: str, resolution: str = "720p",
                 poll_seconds: float = 8.0, timeout_seconds: float = 900.0):
        self.api_key, self.model = api_key, model
        self.resolution = resolution
        self.poll_seconds, self.timeout_seconds = poll_seconds, timeout_seconds

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def animate(self, prompt: str, seconds: float, out: Path,
                first_frame: Path | None = None) -> tuple[Path | None, float]:
        if not self.available:
            return None, 0.0
        body: dict = {
            "model": self.model,
            "prompt": prompt,
            "duration": max(1, min(15, int(round(seconds)))),
            "resolution": self.resolution,
            "aspect_ratio": "9:16",
        }
        if first_frame and first_frame.exists():
            uri = "data:image/jpeg;base64," + base64.b64encode(first_frame.read_bytes()).decode()
            body["frame_images"] = [
                {"type": "image_url", "image_url": {"url": uri}, "frame_type": "first_frame"}
            ]
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(f"{OPENROUTER}/videos", json=body, headers=headers)
                _raise_if_out_of_credits(resp)
                if resp.status_code >= 400:
                    log.warning("video submit -> %s %s", resp.status_code, resp.text[:300])
                    return None, 0.0
                job = resp.json()
                job_id, started = job.get("id"), time.time()
                while job.get("status") not in ("completed", "succeeded", "failed", "error", "cancelled"):
                    if time.time() - started > self.timeout_seconds:
                        log.warning("video job %s timed out", job_id)
                        return None, 0.0
                    time.sleep(self.poll_seconds)
                    poll = client.get(f"{OPENROUTER}/videos/{job_id}", headers=headers)
                    if poll.status_code >= 400:
                        return None, 0.0
                    job = poll.json()

                cost = float((job.get("usage") or {}).get("cost") or 0.0)
                if job.get("status") not in ("completed", "succeeded"):
                    return None, cost
                urls = job.get("unsigned_urls") or []
                if not urls:
                    return None, cost
                # The "unsigned" URL still requires the bearer token.
                content = client.get(urls[0], headers=headers)
                if content.status_code >= 400:
                    return None, cost
                out.write_bytes(content.content)
                return out, cost
        except OutOfCredits:
            raise
        except Exception:  # noqa: BLE001
            log.exception("video generation failed")
            return None, 0.0


class StubVideoProvider:
    """Animates the keyframe locally. Free, offline, always available."""

    available = True

    def animate(self, prompt: str, seconds: float, out: Path,
                first_frame: Path | None = None) -> tuple[Path | None, float]:
        if not first_frame or not Path(first_frame).exists():
            return None, 0.0
        try:
            return media.ken_burns(first_frame, seconds, out), 0.0
        except media.MediaError:
            log.exception("ken burns fallback failed")
            return None, 0.0


# ----------------------------------------------------------------- factories

def text_client() -> TextClient | NullTextClient:
    """The planner's client — a capable model; script quality starts here."""
    key = getattr(settings, "OPENAI_API_KEY", "")
    if not key:
        return NullTextClient()
    return TextClient(key, getattr(settings, "OPENAI_PLAN_MODEL", "gpt-4.1"))


def review_client() -> TextClient | NullTextClient:
    """The keyframe reviewer — a cheap vision model; it only fills a rubric."""
    key = getattr(settings, "OPENAI_API_KEY", "")
    if not key:
        return NullTextClient()
    return TextClient(key, getattr(settings, "OPENAI_REVIEW_MODEL", "gpt-4o-mini"))


def image_provider():
    mode = getattr(settings, "IMAGE_PROVIDER", "stub")
    key = getattr(settings, "OPENROUTER_API_KEY", "")
    if mode == "openrouter" and key:
        return ImageProvider(key, getattr(settings, "IMAGE_MODEL", ""))
    return StubImageProvider()


def video_provider(resolution: str | None = None):
    """`resolution` is the per-clip choice (720p free, 1080p Creator);
    VIDEO_RESOLUTION remains the default for callers that don't pass one."""
    mode = getattr(settings, "VIDEO_PROVIDER", "stub")
    key = getattr(settings, "OPENROUTER_API_KEY", "")
    if mode == "openrouter" and key:
        return VideoProvider(
            key,
            getattr(settings, "VIDEO_MODEL", ""),
            resolution or getattr(settings, "VIDEO_RESOLUTION", "720p"),
        )
    return StubVideoProvider()
