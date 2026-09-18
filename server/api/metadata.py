"""Metadata API endpoints: title, cover art operations."""

from __future__ import annotations

import os
import shutil
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response

from server.main import SESSION, invalidate_track_cache
from server.models.schemas import SetTitleRequest
from server.utils.async_utils import run_blocking

router = APIRouter()


def _get_track_path(track_id: str) -> str:
    fpath = SESSION["track_files"].get(track_id)
    if not fpath or not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail=f"Track {track_id} not found")
    return fpath


def _atomic_replace(src: str, dst: str) -> bool:
    """Atomically replace dst with src, creating a backup of dst first.

    Uses save_with_backup from src.utils.file_ops for atomic replacement.
    Returns True on success, False on failure (original dst is restored).
    """
    try:
        from src.utils.file_ops import save_with_backup
        save_with_backup(src, dst)
        return True
    except Exception:
        return False


# ── Read title ───────────────────────────────────────────────────────


@router.get("/tracks/{track_id}/metadata/title")
async def get_title(track_id: str):
    """Read the title metadata from a track."""
    fpath = _get_track_path(track_id)
    try:
        from src.audio.metadata import read_title_metadata
        title = await run_blocking(read_title_metadata, fpath)
        return {"track_id": track_id, "title": title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Set title ────────────────────────────────────────────────────────


@router.put("/tracks/{track_id}/metadata/title")
async def set_title(track_id: str, req: SetTitleRequest):
    """Set the title metadata on a track (with atomic backup)."""
    fpath = _get_track_path(track_id)

    # Create a temp copy, modify it, then atomically replace the original
    ext = os.path.splitext(fpath)[1]
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    try:
        shutil.copy2(fpath, tmp_path)

        from src.audio.metadata import set_title_metadata
        success = await run_blocking(set_title_metadata, tmp_path, req.title)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to set title metadata")

        # Atomically replace original with modified temp (creates backup)
        if not _atomic_replace(tmp_path, fpath):
            raise HTTPException(status_code=500, detail="Failed to save safely")

        invalidate_track_cache(track_id)
        return {"track_id": track_id, "title": req.title, "success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ── Get cover art ────────────────────────────────────────────────────


@router.get("/tracks/{track_id}/cover")
async def get_cover(track_id: str):
    """Extract and return the cover art image from a track."""
    fpath = _get_track_path(track_id)
    try:
        from src.audio.metadata import extract_cover_art
        cover_path = await run_blocking(extract_cover_art, fpath)
        if not cover_path or not os.path.exists(cover_path):
            raise HTTPException(status_code=404, detail="No cover art found")

        ext = os.path.splitext(cover_path)[1].lower()
        media_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
        }.get(ext, "application/octet-stream")

        with open(cover_path, "rb") as f:
            data = f.read()
        os.remove(cover_path)
        return Response(content=data, media_type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Set cover art ────────────────────────────────────────────────────


@router.post("/tracks/{track_id}/cover")
async def set_cover(track_id: str, file: UploadFile = File(...)):
    """Set the cover art on a track (with atomic backup)."""
    fpath = _get_track_path(track_id)

    # Save uploaded image to temp file
    ext = os.path.splitext(file.filename or "cover.jpg")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".bmp"):
        raise HTTPException(status_code=400, detail="Unsupported image format")

    fd, img_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    try:
        content = await file.read()
        with open(img_path, "wb") as f:
            f.write(content)

        # Create temp copy of original, modify it, then atomically replace
        orig_ext = os.path.splitext(fpath)[1]
        fd2, tmp_copy = tempfile.mkstemp(suffix=orig_ext)
        os.close(fd2)
        try:
            shutil.copy2(fpath, tmp_copy)

            from src.audio.metadata import set_cover_art
            success = await run_blocking(set_cover_art, tmp_copy, img_path)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to set cover art")

            if not _atomic_replace(tmp_copy, fpath):
                raise HTTPException(status_code=500, detail="Failed to save safely")

            invalidate_track_cache(track_id)
            return {"track_id": track_id, "success": True}
        finally:
            if os.path.exists(tmp_copy):
                os.remove(tmp_copy)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


# ── Get all metadata ─────────────────────────────────────────────────


@router.get("/tracks/{track_id}/metadata")
async def get_all_metadata(track_id: str):
    """Get all available metadata for a track."""
    fpath = _get_track_path(track_id)
    try:
        from src.audio.metadata import (
            read_title_metadata,
            get_duration_ffprobe,
        )
        title = await run_blocking(read_title_metadata, fpath)
        duration = await run_blocking(get_duration_ffprobe, fpath)

        has_cover = False
        from src.audio.metadata import extract_cover_art
        cover_path = await run_blocking(extract_cover_art, fpath)
        if cover_path:
            has_cover = True
            try:
                os.remove(cover_path)
            except OSError:
                pass

        return {
            "track_id": track_id,
            "file_name": os.path.basename(fpath),
            "title": title,
            "duration_seconds": duration,
            "has_cover": has_cover,
            "format": os.path.splitext(fpath)[1].lstrip("."),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
