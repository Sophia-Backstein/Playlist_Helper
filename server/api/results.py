"""Results API — endpoints for downloading and managing processing results."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from server.main import SESSION

router = APIRouter()


@router.get("/results/{result_id}/download", response_model=None)
async def download_result(result_id: str):
    """Download a processing result file by result ID.

    Reads the file immediately, deletes it, and removes the session entry,
    ensuring single-use semantics without race conditions.
    """
    rinfo = SESSION.get("results", {}).get(result_id)
    if rinfo is None:
        raise HTTPException(status_code=404, detail="Result not found")

    file_path = rinfo.get("file_path")
    original_name = rinfo.get("original_name", "output.mp3")

    if not file_path or not os.path.isfile(file_path):
        # Clean up stale session entry
        SESSION.get("results", {}).pop(result_id, None)
        raise HTTPException(status_code=404, detail="Result file not found")

    # Read file content immediately, before any deletion
    with open(file_path, "rb") as f:
        data = f.read()

    # Delete the file now (not via background task — avoids race with
    # concurrent requests that might start streaming before deletion)
    try:
        os.remove(file_path)
    except OSError:
        pass

    # Remove from session — subsequent requests get 404
    SESSION.get("results", {}).pop(result_id, None)

    # Determine media type from extension
    ext = Path(original_name).suffix.lower()
    media_map = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
    }
    media_type = media_map.get(ext, "application/octet-stream")

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{original_name}"'},
    )


@router.get("/results/{result_id}/info")
async def get_result_info(result_id: str):
    """Get metadata about a processing result."""
    rinfo = SESSION.get("results", {}).get(result_id)
    if rinfo is None:
        raise HTTPException(status_code=404, detail="Result not found")

    return {
        "result_id": result_id,
        "original_name": rinfo.get("original_name"),
        "file_path": rinfo.get("file_path"),
        "track_id": rinfo.get("track_id"),
        "operation": rinfo.get("operation"),
        "exists": os.path.isfile(rinfo["file_path"]) if rinfo.get("file_path") else False,
    }
