"""Track management API endpoints: scan, upload, list, get, delete, rename."""

from __future__ import annotations

import os
import shutil
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse

from server.main import SESSION, get_workspace, next_track_id, invalidate_track_cache
from server.utils.async_utils import run_blocking
from server.models.schemas import (
    TrackInfo,
    TrackListResponse,
    ScanRequest,
    ScanResponse,
    RenameRequest,
)

router = APIRouter()

# Supported extensions (mirrors src/audio/scanner.py)
SUPPORTED_AUDIO = {".mp3", ".m4a", ".opus", ".wav", ".flac"}
SUPPORTED_VIDEO = {".mp4", ".avi", ".flv", ".mkv", ".webm", ".mov"}
SUPPORTED_ALL = SUPPORTED_AUDIO | SUPPORTED_VIDEO

# Max upload size: 500 MB
MAX_UPLOAD_SIZE = 500 * 1024 * 1024


def _is_supported(ext: str) -> bool:
    return ext.lower() in SUPPORTED_ALL


def _is_video(ext: str) -> bool:
    return ext.lower() in SUPPORTED_VIDEO


def _is_audio(ext: str) -> bool:
    return ext.lower() in SUPPORTED_AUDIO


def _get_media_type(ext: str) -> str:
    return "video" if _is_video(ext) else "audio"


async def _build_track_info(file_path: str, track_id: str, use_cache: bool = True) -> TrackInfo:
    """Build a TrackInfo from a file path, using cache if available.

    The cache key includes file modification time to detect stale entries.
    """
    # Check cache
    if use_cache and track_id in SESSION.get("track_info_cache", {}):
        cached = SESSION["track_info_cache"][track_id]
        # Validate cache is fresh — compare with current file mtime
        try:
            current_mtime = os.path.getmtime(file_path)
            if cached.get("_mtime") == current_mtime:
                return cached["info"]
        except OSError:
            pass
        # Stale cache — rebuild below

    name = os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    # Try to get duration
    try:
        from src.audio.metadata import get_duration_ffprobe
        duration = await run_blocking(get_duration_ffprobe, file_path)
    except Exception:
        duration = 0.0

    # Try to get title
    title = ""
    try:
        from src.audio.metadata import read_title_metadata
        title = await run_blocking(read_title_metadata, file_path)
    except Exception:
        pass

    # Try volume analysis
    mean_db = 0.0
    cleaned_db = 0.0
    max_db = 0.0
    try:
        from src.audio.analyzer import analyze_volume_ffmpeg, compute_cleaned_average
        vol = await run_blocking(analyze_volume_ffmpeg, file_path)
        mean_db = vol.get("mean_volume", 0.0)
        max_db = vol.get("max_volume", 0.0)
        cleaned_db = await run_blocking(compute_cleaned_average, file_path)
    except Exception:
        pass

    # Check cover
    has_cover = False
    try:
        from src.audio.metadata import extract_cover_art
        cover = await run_blocking(extract_cover_art, file_path)
        if cover:
            has_cover = True
            try:
                os.remove(cover)
            except OSError:
                pass
    except Exception:
        pass

    fmt = ext.lstrip(".")
    info = TrackInfo(
        track_id=track_id,
        file_name=name,
        file_path=file_path,
        duration_seconds=duration,
        format=fmt,
        media_type=_get_media_type(ext),
        title=title,
        average_volume_db=mean_db,
        cleaned_average_db=cleaned_db,
        max_volume_db=max_db,
        has_cover=has_cover,
        size_bytes=size,
    )

    # Store in cache
    try:
        SESSION.setdefault("track_info_cache", {})[track_id] = {
            "info": info,
            "_mtime": os.path.getmtime(file_path),
        }
    except OSError:
        pass

    return info


def _validate_path_in_workspace(resolved: str, workspace: str) -> None:
    """Raise HTTP 400 if resolved path is outside the workspace directory."""
    real_resolved = os.path.realpath(resolved)
    real_workspace = os.path.realpath(workspace)
    if not real_resolved.startswith(real_workspace + os.sep) and real_resolved != real_workspace:
        raise HTTPException(
            status_code=400,
            detail="Path traversal detected: target path is outside workspace",
        )


# ── Scan folder ────────────────────────────────────────────────────


@router.post("/scan", response_model=ScanResponse)
async def scan_folder(req: ScanRequest):
    """Scan a folder on the server for media files."""
    folder = req.folder_path
    if not os.path.isdir(folder):
        raise HTTPException(status_code=400, detail=f"Folder not found: {folder}")

    try:
        from src.audio.scanner import scan_folder as scan
        files = scan(folder)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}")

    tracks: list[TrackInfo] = []
    for fpath in files:
        tid = next_track_id()
        SESSION["tracks"][tid] = {"file_path": fpath}
        SESSION["track_files"][tid] = fpath
        info = await _build_track_info(fpath, tid, use_cache=False)
        tracks.append(info)

    return ScanResponse(tracks=tracks, count=len(tracks), folder_path=folder)


# ── Upload files ───────────────────────────────────────────────────


@router.post("/upload", response_model=TrackListResponse)
async def upload_files(files: list[UploadFile] = File(...)):
    """Upload media files to the workspace."""
    ws = get_workspace()
    tracks: list[TrackInfo] = []

    for upload in files:
        ext = os.path.splitext(upload.filename or "")[1].lower()
        if not _is_supported(ext):
            continue

        tid = next_track_id()
        safe_name = f"{tid}_{upload.filename}"
        dest = os.path.join(ws, safe_name)

        # Prevent path traversal: reject filenames that escape the workspace
        _validate_path_in_workspace(dest, ws)

        # Stream to disk in 64KB chunks, checking size as we go
        # (never loads the entire file into memory)
        with open(dest, "wb") as f:
            total = 0
            while chunk := await upload.read(64 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_SIZE:
                    f.close()
                    os.remove(dest)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File {upload.filename} exceeds maximum upload size of 500 MB",
                    )
                f.write(chunk)

        SESSION["tracks"][tid] = {"file_path": dest}
        SESSION["track_files"][tid] = dest
        info = await _build_track_info(dest, tid, use_cache=False)
        tracks.append(info)

    return TrackListResponse(tracks=tracks, count=len(tracks))


# ── List tracks ────────────────────────────────────────────────────


@router.get("/tracks", response_model=TrackListResponse)
async def list_tracks():
    """List all tracks in the current session."""
    tracks: list[TrackInfo] = []
    for tid, fpath in list(SESSION["track_files"].items()):
        if os.path.exists(fpath):
            info = await _build_track_info(fpath, tid, use_cache=True)
            tracks.append(info)
        else:
            # Clean up stale entries
            SESSION["tracks"].pop(tid, None)
            SESSION["track_files"].pop(tid, None)
            invalidate_track_cache(tid)
    return TrackListResponse(tracks=tracks, count=len(tracks))


# ── Get single track ───────────────────────────────────────────────


@router.get("/tracks/{track_id}", response_model=TrackInfo)
async def get_track(track_id: str):
    """Get detailed information about a single track."""
    fpath = SESSION["track_files"].get(track_id)
    if not fpath or not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail=f"Track {track_id} not found")
    return await _build_track_info(fpath, track_id, use_cache=True)


# ── Delete track ───────────────────────────────────────────────────


@router.delete("/tracks/{track_id}")
async def delete_track(track_id: str):
    """Remove a track from the session (does not delete the file)."""
    if track_id not in SESSION["track_files"]:
        raise HTTPException(status_code=404, detail=f"Track {track_id} not found")
    SESSION["tracks"].pop(track_id, None)
    SESSION["track_files"].pop(track_id, None)
    invalidate_track_cache(track_id)
    return {"status": "deleted", "track_id": track_id}


# ── Stream track (for audio playback in browser) ──────────────────


MEDIA_TYPE_MAP = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".opus": "audio/ogg",
    ".ogg": "audio/ogg",
    ".mp4": "audio/mp4",
    ".webm": "audio/webm",
}


@router.get("/tracks/{track_id}/stream", response_model=None)
async def stream_track(track_id: str):
    """Stream a track for in-browser audio playback (no download headers)."""
    fpath = SESSION["track_files"].get(track_id)
    if not fpath or not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

    ext = os.path.splitext(fpath)[1].lower()
    media_type = MEDIA_TYPE_MAP.get(ext, "application/octet-stream")

    return FileResponse(
        path=fpath,
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        },
    )


# ── Download track ─────────────────────────────────────────────────


@router.get("/tracks/{track_id}/download", response_model=None)
async def download_track(track_id: str, format: Optional[str] = None, background_tasks: BackgroundTasks = None):
    """Download a track. Optionally convert to a different format first.

    Temp files from conversion are cleaned up after download.
    """
    fpath = SESSION["track_files"].get(track_id)
    if not fpath or not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

    if format and format in ("mp3", "wav", "flac"):
        # Convert on-the-fly
        from src.audio.processor import convert_format
        import tempfile
        ext = f".{format}"
        fd, out = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        try:
            ok = await run_blocking(convert_format, fpath, out, format)
            if not ok:
                os.remove(out)
                raise HTTPException(status_code=500, detail="Conversion failed")
            name = os.path.splitext(os.path.basename(fpath))[0] + ext
            # Clean up temp file after download
            if background_tasks is not None:
                background_tasks.add_task(_delete_temp_file, out)
            return FileResponse(out, filename=name, media_type="audio/mpeg")
        except HTTPException:
            if os.path.exists(out):
                os.remove(out)
            raise
        except Exception as e:
            if os.path.exists(out):
                os.remove(out)
            raise HTTPException(status_code=500, detail=str(e))

    name = os.path.basename(fpath)
    return FileResponse(fpath, filename=name)


def _delete_temp_file(path: str) -> None:
    """Safely delete a temp file."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# ── Rename track ───────────────────────────────────────────────────


@router.put("/tracks/{track_id}/rename")
async def rename_track(track_id: str, req: RenameRequest):
    """Rename a track's file on disk.

    Requires the resolved path to stay within the workspace directory
    (prevents path traversal).
    """
    fpath = SESSION["track_files"].get(track_id)
    if not fpath or not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

    # Prevent path traversal in new filename
    if os.path.isabs(req.new_filename) or ".." in req.new_filename.split(os.sep):
        raise HTTPException(
            status_code=400,
            detail="Path traversal detected: new_filename must be a simple filename, not a path",
        )

    old_dir = os.path.dirname(fpath)
    ws = get_workspace()
    new_path = os.path.join(old_dir, req.new_filename)

    # Double-check the resolved path stays within workspace
    _validate_path_in_workspace(new_path, ws)

    if os.path.exists(new_path):
        raise HTTPException(status_code=400, detail="Target filename already exists")

    try:
        os.rename(fpath, new_path)
        SESSION["track_files"][track_id] = new_path
        SESSION["tracks"][track_id] = {"file_path": new_path}
        invalidate_track_cache(track_id)
        return await _build_track_info(new_path, track_id, use_cache=False)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Rename failed: {e}")
