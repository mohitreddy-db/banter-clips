from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, engine
from .routers import auth, billing, clips, events, me, socials


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MVP: create_all keeps the schema in sync with app/models.py.
    # Production/Supabase: apply schema.sql (see DATABASE.md).
    Base.metadata.create_all(bind=engine)
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

app.mount("/media", StaticFiles(directory=settings.MEDIA_DIR), name="media")


@app.get("/health", tags=["ops"])
def health():
    return {"ok": True, "service": "banterclips-api"}
