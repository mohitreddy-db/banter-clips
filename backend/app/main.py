from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db_migrate
from .config import settings
from .db import Base, engine
from .routers import admin, auth, billing, clips, events, me, socials


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MVP: create_all keeps the schema in sync with app/models.py.
    # Production/Supabase: apply schema.sql (see DATABASE.md).
    Base.metadata.create_all(bind=engine)
    # create_all adds missing tables but never alters existing ones, so new
    # columns need this. Additive and idempotent; see db_migrate.
    db_migrate.apply()
    settings.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="BanterClips API",
    version="0.1.0",
    description="Phase 1 MVP backend — opinion → video → publish. "
    "Video generation runs in dummy mode until the provider bake-off completes.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(clips.router)
app.include_router(socials.router)
app.include_router(billing.router)
app.include_router(events.router)
app.include_router(admin.router)

app.mount("/media", StaticFiles(directory=settings.MEDIA_DIR), name="media")


@app.get("/health", tags=["ops"])
def health():
    """Liveness. Deliberately dependency-free so it answers under load."""
    return {"ok": True, "service": "banterclips-api"}


@app.get("/health/ready", tags=["ops"])
def readiness():
    """Readiness: can we reach the database, and is the queue draining?

    Queue depth is the number worth alerting on. A rising `queued` with a flat
    `running` means no worker is alive — the API looks perfectly healthy while
    every clip silently waits forever.
    """
    from .db import SessionLocal
    from .services import jobs

    db = SessionLocal()
    try:
        depth = jobs.depth(db)
        return {
            "ok": True,
            "database": "up",
            "queue_mode": settings.QUEUE_MODE,
            "pipeline_mode": settings.PIPELINE_MODE,
            "storage": settings.STORAGE_BACKEND,
            "queue": depth,
        }
    except Exception as exc:  # noqa: BLE001 — report, do not raise
        return JSONResponse(
            status_code=503,
            content={"ok": False, "database": "down", "error": str(exc)[:200]},
        )
    finally:
        db.close()
