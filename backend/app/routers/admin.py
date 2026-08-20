"""Admin panel API — character catalog management.

Everything here sits behind the ADMIN_EMAILS allow-list, answering 404 to
everyone else. The catalog is two layers (curated JSON in git + DB rows that
override it); these endpoints read the merged view and write the DB layer,
so an admin can edit or deactivate anything — including curated characters —
without a deploy.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..deps import get_admin_user
from ..models import User
from ..security import decode_session_jwt
from ..db import SessionLocal
from ..video import catalog

log = logging.getLogger("banter.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


class CharacterOut(BaseModel):
    id: str
    name: str
    sport: str
    look: str
    default_wardrobe: str
    voice_style: str
    aliases: list[str] = []
    teams: list[str] = []
    active: bool = True
    source: str = "curated"
    # Ready-to-render image URLs: absolute for Storage-hosted stills,
    # API-relative (append your session token) for repo-hosted ones.
    reference_urls: list[str] = []


class CharacterPatch(BaseModel):
    name: str | None = None
    sport: str | None = None
    look: str | None = None
    default_wardrobe: str | None = None
    voice_style: str | None = None
    aliases: list[str] | None = None
    teams: list[str] | None = None
    active: bool | None = None


class CharacterCreate(CharacterPatch):
    id: str | None = None
    name: str = Field(min_length=2, max_length=80)


def _reference_urls(char: catalog.Character) -> list[str]:
    urls = []
    for index, entry in enumerate(char.reference_images):
        if entry.startswith("references/"):
            urls.append(f"/admin/catalog/{char.id}/reference/{index}")
            continue
        try:
            from ..services import storage

            urls.append(storage.get().url(entry))
        except Exception:  # noqa: BLE001 — a missing thumbnail never 500s the list
            log.warning("no URL for reference %s", entry)
    return urls


def _out(char: catalog.Character) -> CharacterOut:
    return CharacterOut(
        id=char.id, name=char.name, sport=char.sport, look=char.look,
        default_wardrobe=char.default_wardrobe, voice_style=char.voice_style,
        aliases=char.aliases, teams=char.teams, active=char.active,
        source=char.source, reference_urls=_reference_urls(char),
    )


@router.get("/catalog", response_model=list[CharacterOut])
def list_catalog(admin: User = Depends(get_admin_user)):
    return [_out(c) for c in catalog.all_characters()]


@router.post("/catalog", response_model=CharacterOut, status_code=201)
def create_character(body: CharacterCreate, admin: User = Depends(get_admin_user)):
    char_id = catalog.slugify(body.id or body.name)
    if not char_id:
        raise HTTPException(422, "A usable id could not be made from that name.")
    if any(c.id == char_id for c in catalog.all_characters()):
        raise HTTPException(409, f"Character '{char_id}' already exists.")
    fields = body.model_dump(exclude_none=True, exclude={"id"})
    saved = catalog.upsert_character(char_id, fields, source="admin")
    if saved is None:
        raise HTTPException(500, "Could not save the character.")
    return _out(saved)


@router.patch("/catalog/{char_id}", response_model=CharacterOut)
def update_character(char_id: str, body: CharacterPatch, admin: User = Depends(get_admin_user)):
    if not any(c.id == char_id for c in catalog.all_characters()):
        raise HTTPException(404, "No such character.")
    saved = catalog.upsert_character(char_id, body.model_dump(exclude_none=True), source="admin")
    if saved is None:
        raise HTTPException(500, "Could not save the character.")
    return _out(saved)


@router.post("/catalog/{char_id}/references", response_model=CharacterOut)
def regenerate_references(char_id: str, admin: User = Depends(get_admin_user)):
    """Generate fresh reference stills (face + full body). REAL SPEND: about
    $0.10 with the production image provider — an explicit admin action."""
    char = next((c for c in catalog.all_characters() if c.id == char_id), None)
    if char is None:
        raise HTTPException(404, "No such character.")
    from ..video import catalog_build, providers

    images = providers.image_provider()
    paths, cost = catalog_build.build_character(char, images)
    if not paths:
        raise HTTPException(502, "Still generation failed — check provider credit.")
    catalog.set_reference_images(char_id, paths)
    log.info("admin %s regenerated references for %s ($%.3f)", admin.email, char_id, cost)
    fresh = next((c for c in catalog.all_characters() if c.id == char_id), char)
    return _out(fresh)


@router.get("/catalog/{char_id}/reference/{index}")
def reference_image(char_id: str, index: int, token: str = ""):
    """Serve a repo-hosted reference still.

    Auth via ?token= (the session JWT) because <img> tags cannot send an
    Authorization header. Same allow-list, same 404-to-outsiders behaviour.
    """
    user_id = decode_session_jwt(token)
    if user_id is None:
        raise HTTPException(404, "Not found")
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
    finally:
        db.close()
    if user is None or user.is_blocked or not user.is_admin:
        raise HTTPException(404, "Not found")

    char = next((c for c in catalog.all_characters() if c.id == char_id), None)
    if char is None or index >= len(char.reference_images):
        raise HTTPException(404, "Not found")
    paths = char.reference_paths()
    if index >= len(paths):
        raise HTTPException(404, "Not found")
    return FileResponse(paths[index], media_type="image/jpeg")
