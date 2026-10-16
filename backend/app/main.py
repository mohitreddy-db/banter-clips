import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db_migrate
from .config import settings
from .db import Base, engine
from .routers import admin, admin_console, auth, billing, clips, events, feedback, me, socials

log = logging.getLogger("banter.api")


class CrashToJSON:
    """Turn an unhandled exception into a JSON 500 that carries CORS headers.

    Starlette's own 500 comes from ServerErrorMiddleware, the outermost layer,
    so it never passes through CORSMiddleware. The browser then withholds the
    response and fetch() rejects as a *network* failure — the app told users
    "can't reach the server" for a crash the server had answered (2026-10-16,
    a DB constraint violation on POST /clips). Sitting inside the CORS layer,
    this reply reaches the page with the real status and a message.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_tracking(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_tracking)
        except Exception:
            log.exception("unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if started:
                raise  # headers are gone; nothing useful left to send
            response = JSONResponse(
                status_code=500,
                content={"detail": {
                    "code": "server_error",
                    "message": "Something went wrong on our side. Please try again in a moment.",
                }},
            )
            await response(scope, receive, send)


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

# add_middleware wraps outward: the last one added runs first. CrashToJSON goes
# in before CORS so CORS sits outside it and stamps its 500 with the headers.
app.add_middleware(CrashToJSON)
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
app.include_router(feedback.router)
app.include_router(admin.router)
app.include_router(admin_console.router)

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
