"""Where generated artifacts live.

One interface, two backends. Local disk for development (no credentials, no
network) and Supabase Storage for production. Choosing between them is an env
var, so nothing above this module knows or cares which is in use.

Key layout:

    users/{user_id}/clips/{clip_id}/final.mp4
    users/{user_id}/clips/{clip_id}/poster.jpg
    users/{user_id}/clips/{clip_id}/scene0_kf1.jpg
    ...

`user_id` is not needed to find anything — the database has that — but it makes
two otherwise painful operations trivial: deleting everything belonging to one
person (account closure), and attributing storage per user.

Retention is by tier, because a 15s clip produces ~51 MB of which ~14 MB is
worth keeping (measured). Deliverables live as long as the clip; keyframes are
evidence for a month; the per-scene and intermediate video files are scratch
and expire in a week. `purge_scratch` implements that.

The final MP4 must be publicly readable: Instagram fetches it from a URL at
publish time and cannot present credentials. Keys are UUID-based and therefore
unguessable, which is the protection. Everything else stays private.
"""

from __future__ import annotations

import logging
import mimetypes
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

from ..config import settings

log = logging.getLogger("banter.storage")

# Retention per tier, in days. 0 means "keep until the clip is deleted".
KEEP_FOREVER = 0
RETENTION_DAYS = {
    "deliverable": KEEP_FOREVER,   # final.mp4, poster.jpg
    "evidence": 30,                # approved keyframes
    "scratch": 7,                  # scene clips, normalised copies, joined cut
}

# Which files belong to which tier, by filename.
_DELIVERABLES = ("final.mp4", "poster.jpg")


def tier_for(name: str) -> str:
    if name in _DELIVERABLES:
        return "deliverable"
    if name.endswith(".jpg") or name.endswith(".jpeg") or name.endswith(".png"):
        return "evidence"
    if name.endswith(".json") or name.endswith(".txt"):
        return "evidence"
    return "scratch"


def clip_prefix(user_id: uuid.UUID | str, clip_id: uuid.UUID | str) -> str:
    return f"users/{user_id}/clips/{clip_id}"


@dataclass
class StoredObject:
    key: str
    url: str
    bytes: int


class Storage:
    """Interface. Implementations must never raise on a missing object."""

    def put(self, key: str, source: Path | bytes, content_type: str = "") -> StoredObject:
        raise NotImplementedError

    def url(self, key: str) -> str:
        raise NotImplementedError

    def local_path(self, key: str) -> Path | None:
        """A readable path, if the backend can produce one cheaply."""
        return None

    def open(self, key: str) -> bytes | None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def delete_prefix(self, prefix: str) -> int:
        raise NotImplementedError

    def purge_scratch(self, older_than_days: int = RETENTION_DAYS["scratch"]) -> int:
        raise NotImplementedError


class LocalStorage(Storage):
    """Files under MEDIA_DIR, served by the app's /media static mount."""

    def __init__(self, root: Path, base_url: str):
        self.root = Path(root)
        self.base_url = base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        # Defence against a key escaping the root via "..".
        target = (self.root / key).resolve()
        if not str(target).startswith(str(self.root.resolve())):
            raise ValueError(f"refusing key outside the media root: {key!r}")
        return target

    def put(self, key: str, source: Path | bytes, content_type: str = "") -> StoredObject:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(source, (bytes, bytearray)):
            path.write_bytes(source)
        else:
            shutil.copyfile(source, path)
        return StoredObject(key=key, url=self.url(key), bytes=path.stat().st_size)

    def url(self, key: str) -> str:
        return f"{self.base_url}/media/{key}"

    def local_path(self, key: str) -> Path | None:
        path = self._path(key)
        return path if path.exists() else None

    def open(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.exists() else None

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def delete_prefix(self, prefix: str) -> int:
        base = self._path(prefix)
        if not base.exists():
            return 0
        count = sum(1 for p in base.rglob("*") if p.is_file())
        shutil.rmtree(base, ignore_errors=True)
        return count

    def purge_scratch(self, older_than_days: int = RETENTION_DAYS["scratch"]) -> int:
        cutoff = time.time() - older_than_days * 86400
        removed = 0
        for path in self.root.rglob("*"):
            if not path.is_file() or tier_for(path.name) != "scratch":
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                log.warning("could not purge %s", path)
        return removed


class SupabaseStorage(Storage):
    """Supabase Storage over its REST API.

    Chosen because Supabase is already a dependency (auth), so production adds
    no new vendor or credential. The interface is deliberately small enough
    that swapping in S3/R2 is one class, not a refactor.
    """

    def __init__(self, base_url: str, service_key: str, bucket: str, timeout: float = 60.0):
        self.base = base_url.rstrip("/")
        self.key = service_key
        self.bucket = bucket
        self.timeout = timeout

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.key}"}

    def _object_url(self, key: str) -> str:
        return f"{self.base}/storage/v1/object/{self.bucket}/{key}"

    def put(self, key: str, source: Path | bytes, content_type: str = "") -> StoredObject:
        payload = source if isinstance(source, (bytes, bytearray)) else Path(source).read_bytes()
        ctype = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                self._object_url(key),
                content=payload,
                headers={**self._headers, "content-type": ctype, "x-upsert": "true"},
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"upload failed {resp.status_code}: {resp.text[:200]}")
        return StoredObject(key=key, url=self.url(key), bytes=len(payload))

    def url(self, key: str) -> str:
        # Public read on an unguessable key: Instagram's fetcher cannot sign.
        return f"{self.base}/storage/v1/object/public/{self.bucket}/{key}"

    def open(self, key: str) -> bytes | None:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(self._object_url(key), headers=self._headers)
        return resp.content if resp.status_code < 400 else None

    def delete(self, key: str) -> None:
        with httpx.Client(timeout=self.timeout) as client:
            client.request("DELETE", self._object_url(key), headers=self._headers)

    def _list(self, prefix: str) -> list[str]:
        names: list[str] = []
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base}/storage/v1/object/list/{self.bucket}",
                json={"prefix": prefix, "limit": 1000},
                headers={**self._headers, "content-type": "application/json"},
            )
            if resp.status_code < 400:
                for item in resp.json() or []:
                    if item.get("name"):
                        names.append(f"{prefix}/{item['name']}".strip("/"))
        return names

    def delete_prefix(self, prefix: str) -> int:
        keys = self._list(prefix)
        if not keys:
            return 0
        with httpx.Client(timeout=self.timeout) as client:
            client.request(
                "DELETE", f"{self.base}/storage/v1/object/{self.bucket}",
                json={"prefixes": keys},
                headers={**self._headers, "content-type": "application/json"},
            )
        return len(keys)

    def purge_scratch(self, older_than_days: int = RETENTION_DAYS["scratch"]) -> int:
        """Nothing to do: scratch is never uploaded.

        `_store_artifacts` only sends deliverables and approved keyframes; the
        per-scene clips and rejected frames stay in the local working directory
        and housekeeping deletes them there. Evidence expiry is handled by
        `purge_evidence`, which is driven from the database — Supabase Storage
        has no lifecycle rules, so age has to come from the clip row.
        """
        return 0


_backend: Storage | None = None


def get() -> Storage:
    """The configured backend. Falls back to local disk if misconfigured."""
    global _backend
    if _backend is not None:
        return _backend

    mode = str(getattr(settings, "STORAGE_BACKEND", "local")).lower()
    if mode == "supabase":
        url = getattr(settings, "SUPABASE_URL", "")
        key = getattr(settings, "SUPABASE_SERVICE_KEY", "")
        bucket = getattr(settings, "STORAGE_BUCKET", "clips")
        if url and key:
            _backend = SupabaseStorage(url, key, bucket)
            return _backend
        log.error("STORAGE_BACKEND=supabase but URL/service key missing; using local disk")

    _backend = LocalStorage(settings.MEDIA_DIR, settings.API_BASE_URL)
    return _backend


def reset() -> None:
    """Drop the cached backend (tests, or after changing settings)."""
    global _backend
    _backend = None
