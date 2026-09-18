"""Playlist Helper API — FastAPI server exposing all audio processing functions.

Run with:
    python -m server.main
    # or
    uvicorn server.main:app --host 0.0.0.0 --port 9999
"""

from __future__ import annotations

import os
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Session state (in-memory, single-user) ──────────────────────────
# workspace: directory where uploaded/copied files live
# tracks: dict[track_id, dict] storing track metadata
# track_files: dict[track_id, str] mapping track_id to file path
# results: dict[result_id, dict] storing processing/equalize results
# track_info_cache: dict[track_id, TrackInfo] caching expensive analysis
# next_id: auto-incrementing ID counter

SESSION: dict = {
    "workspace": None,
    "tracks": {},
    "track_files": {},
    "results": {},
    "track_info_cache": {},
    "next_track_id": 1,
    "next_result_id": 1,
}


def get_workspace() -> str:
    """Get or create the session workspace directory."""
    if SESSION["workspace"] is None:
        ws = tempfile.mkdtemp(prefix="playlist_helper_ws_")
        SESSION["workspace"] = ws
    return SESSION["workspace"]


def cleanup_workspace() -> None:
    """Remove the workspace directory and all temp files."""
    ws = SESSION.get("workspace")
    if ws and os.path.isdir(ws):
        import shutil
        shutil.rmtree(ws, ignore_errors=True)
        SESSION["workspace"] = None

    # Also clean up any registered result files
    for rid, rinfo in list(SESSION.get("results", {}).items()):
        fpath = rinfo.get("file_path")
        if fpath and os.path.exists(fpath):
            try:
                os.remove(fpath)
            except OSError:
                pass
    SESSION["results"] = {}


def next_track_id() -> str:
    """Generate a unique track ID."""
    tid = str(SESSION["next_track_id"])
    SESSION["next_track_id"] += 1
    return tid


def next_result_id() -> str:
    """Generate a unique result ID."""
    rid = str(SESSION["next_result_id"])
    SESSION["next_result_id"] += 1
    return rid


def invalidate_track_cache(track_id: str) -> None:
    """Invalidate the cached track info for a track."""
    SESSION["track_info_cache"].pop(track_id, None)


# ── Lifespan ────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs(get_workspace(), exist_ok=True)
    yield
    # Shutdown
    cleanup_workspace()


# ── App creation ────────────────────────────────────────────────────

app = FastAPI(
    title="Playlist Helper API",
    version="1.0.0",
    description="Web API for the Playlist Helper audio processing application",
    lifespan=lifespan,
)

# CORS — allow all origins for local/tailscale use
# NOTE: allow_credentials=False is required when allow_origins=["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static file serving ────────────────────────────────────────────

static_dir = Path(__file__).parent / "web" / "static"
static_dir.mkdir(parents=True, exist_ok=True)

# Serve index.html at root
from fastapi.responses import FileResponse


@app.get("/")
async def serve_index():
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"error": "Frontend not built"}


# Mount static files for CSS/JS
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── Include API routers ────────────────────────────────────────────
# NOTE: When running as __main__, alias server.main to avoid circular imports
if __name__ == "__main__":
    import sys
    sys.modules["server.main"] = sys.modules["__main__"]

from server.api.tracks import router as tracks_router
from server.api.process import router as process_router
from server.api.analyze import router as analyze_router
from server.api.equalize import router as equalize_router
from server.api.metadata import router as metadata_router
from server.api.results import router as results_router

app.include_router(tracks_router, prefix="/api")
app.include_router(process_router, prefix="/api")
app.include_router(analyze_router, prefix="/api")
app.include_router(equalize_router, prefix="/api")
app.include_router(metadata_router, prefix="/api")
app.include_router(results_router, prefix="/api")


# ── Health / Info ──────────────────────────────────────────────────

from server.models.schemas import InfoResponse


@app.get("/api/info", response_model=InfoResponse)
async def get_info():
    return InfoResponse()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/live")
async def live():
    return {"status": "ok"}


@app.get("/ident")
async def ident():
    return {"name": "Playlist Helper", "port": 9999, "version": "1.0.0"}


# ── CLI entry point ────────────────────────────────────────────────

def main():
    import uvicorn
    print("Playlist Helper API starting...")
    print(f"   Workspace: {get_workspace()}")
    print(f"   Listening on http://0.0.0.0:9999")
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=9999,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
