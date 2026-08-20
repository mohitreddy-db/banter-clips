"""Admin panel API — character catalog management.

Everything here sits behind the ADMIN_EMAILS allow-list, answering 404 to
everyone else. The catalog is two layers (curated JSON in git + DB rows that
override it); these endpoints read the merged view and write the DB layer,
so an admin can edit or deactivate anything — including curated characters —
without a deploy.
"""

from __future__ import annotations

import logging
from pathlib import Path

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


class GenerateRequest(BaseModel):
    # Admin direction folded into the generation prompt: era, exact kit,
    # hair, anything ("2005 Barcelona home kit, long curly hair, headband").
    notes: str = Field(default="", max_length=500)


class StillOut(BaseModel):
    id: str
    kind: str
    url: str
    notes: str = ""
    source: str = "admin"
    active: bool = False
    created_at: str = ""


class SelectionRequest(BaseModel):
    still_ids: list[str] = Field(min_length=1, max_length=4)


def _still_entry(row) -> str:
    """The durable entry a still contributes to reference_images."""
    return row.storage_key or row.local_path or ""


def _still_out(row, active_entries: set[str]) -> StillOut:
    url = ""
    if row.storage_key:
        try:
            from ..services import storage

            url = storage.get().url(row.storage_key)
        except Exception:  # noqa: BLE001
            pass
    if not url:
        url = f"/admin/stills/{row.id}/image"
    return StillOut(
        id=str(row.id), kind=row.kind, url=url, notes=row.notes or "",
        source=row.source, active=_still_entry(row) in active_entries,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


@router.get("/catalog/{char_id}/stills", response_model=list[StillOut])
def list_stills(char_id: str, admin: User = Depends(get_admin_user)):
    char = next((c for c in catalog.all_characters() if c.id == char_id), None)
    if char is None:
        raise HTTPException(404, "No such character.")
    rows = catalog.stills_for(char_id)
    if not rows and char.reference_images:
        # Curated characters predate the history table — import their active
        # stills as history rows once, so they're selectable like any batch.
        for entry in char.reference_images:
            kind = catalog.still_kind(entry)
            if entry.startswith("references/"):
                catalog.record_still(char_id, kind, local_path=entry, source="curated")
            else:
                catalog.record_still(char_id, kind, storage_key=entry, source="curated")
        rows = catalog.stills_for(char_id)
    active = set(char.reference_images)
    return [_still_out(r, active) for r in rows]


@router.post("/catalog/{char_id}/references", response_model=list[StillOut])
def generate_references(char_id: str, body: GenerateRequest,
                        admin: User = Depends(get_admin_user)):
    """Generate fresh reference stills (face + full body). REAL SPEND: about
    $0.10. The results are CANDIDATES in the history — nothing changes on
    the character until a selection is approved."""
    char = next((c for c in catalog.all_characters() if c.id == char_id), None)
    if char is None:
        raise HTTPException(404, "No such character.")
    from ..video import catalog_build, providers

    images = providers.image_provider()
    paths, cost = catalog_build.build_character(char, images, notes=body.notes)
    if not paths:
        raise HTTPException(502, "Still generation failed — check provider credit.")
    catalog.save_candidate_stills(char_id, paths, notes=body.notes)
    log.info("admin %s generated stills for %s ($%.3f) notes=%r",
             admin.email, char_id, cost, body.notes)
    active = set(char.reference_images)
    fresh_ids = {Path(p).name for p in paths}
    return [_still_out(r, active) for r in catalog.stills_for(char_id)
            if (r.local_path or "").split("/")[-1] in fresh_ids]


@router.put("/catalog/{char_id}/references", response_model=CharacterOut)
def approve_reference_selection(char_id: str, body: SelectionRequest,
                                admin: User = Depends(get_admin_user)):
    """Approve: the chosen history stills become the character's active
    references, used by every future generation."""
    rows = {str(r.id): r for r in catalog.stills_for(char_id)}
    entries = []
    for sid in body.still_ids:
        row = rows.get(sid)
        if row is None or not _still_entry(row):
            raise HTTPException(404, f"No such still {sid}.")
        entries.append(_still_entry(row))
    saved = catalog.apply_reference_selection(char_id, entries)
    if saved is None:
        raise HTTPException(500, "Could not apply the selection.")
    log.info("admin %s approved %d stills for %s", admin.email, len(entries), char_id)
    return _out(saved)


class ResearchOut(BaseModel):
    found: bool
    look: str = ""
    default_wardrobe: str = ""
    voice_style: str = ""


@router.post("/catalog/{char_id}/research", response_model=ResearchOut)
def research_character(char_id: str, admin: User = Depends(get_admin_user)):
    """One web-search call for the REAL details — exact kit colours, crest,
    number, appearance. Returns suggestions; nothing is saved until the
    admin saves the fields."""
    char = next((c for c in catalog.all_characters() if c.id == char_id), None)
    if char is None:
        raise HTTPException(404, "No such character.")
    from ..video import research
    from ..video.types import CastMember

    member = CastMember(id=char.id, name=char.name, look="", wardrobe="", voice="")
    if not research.enabled():
        raise HTTPException(503, "Web research is not configured on this server.")
    found = research.enrich_member(member, char.sport)
    return ResearchOut(found=found, look=member.look if found else "",
                       default_wardrobe=member.wardrobe if found else "",
                       voice_style=member.voice if found else "")


@router.get("/stills/{still_id}/image")
def still_image(still_id: str, token: str = ""):
    """Serve a history still that has no public Storage URL (local-only)."""
    user_id = decode_session_jwt(token)
    if user_id is None:
        raise HTTPException(404, "Not found")
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        from ..models import CatalogStill
        import uuid as _uuid

        try:
            row = db.get(CatalogStill, _uuid.UUID(still_id))
        except ValueError:
            row = None
    finally:
        db.close()
    if user is None or user.is_blocked or not user.is_admin or row is None:
        raise HTTPException(404, "Not found")
    if row.local_path:
        path = catalog.CATALOG_DIR / row.local_path
        if path.exists():
            return FileResponse(path, media_type="image/jpeg")
    raise HTTPException(404, "Not found")


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
