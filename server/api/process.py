"""Processing API endpoints: trim, convert, combined process."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
import tempfile

from server.main import SESSION, next_result_id
from server.utils.async_utils import run_blocking
from server.models.schemas import (
    TrimRequest,
    ConvertRequest,
    ProcessRequest,
    ProcessResult,
)

router = APIRouter()


def _get_track_path(track_id: str) -> str:
    """Get the file path for a track, raising 404 if missing."""
    fpath = SESSION["track_files"].get(track_id)
    if not fpath or not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail=f"Track {track_id} not found")
    return fpath


def _make_temp_output(prefix: str = "proc_", suffix: str = ".mp3") -> str:
    """Create a temp file within the workspace directory for cleanup on shutdown."""
    from server.main import get_workspace
    ws = get_workspace()
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=ws)
    os.close(fd)
    return path


def _store_result(file_path: str, original_name: str, track_id: str, operation: str) -> str:
    """Store a processing result in the session and return a result_id."""
    rid = next_result_id()
    SESSION.setdefault("results", {})[rid] = {
        "file_path": file_path,
        "original_name": original_name,
        "track_id": track_id,
        "operation": operation,
    }
    return rid


def _cleanup_temp(path: str) -> None:
    """Remove a temp file if it exists."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# ── Trim ─────────────────────────────────────────────────────────────


@router.post("/tracks/{track_id}/trim", response_model=ProcessResult)
async def trim_track(track_id: str, req: TrimRequest):
    """Trim a track to the specified time range."""
    fpath = _get_track_path(track_id)

    if req.end_time <= req.start_time:
        raise HTTPException(
            status_code=400,
            detail="end_time must be greater than start_time",
        )

    ext = os.path.splitext(fpath)[1].lower()
    output = _make_temp_output(prefix="trim_", suffix=ext)

    try:
        from src.audio.processor import trim_audio
        success = await run_blocking(trim_audio, fpath, output, req.start_time, req.end_time)
        if not success:
            _cleanup_temp(output)
            raise HTTPException(status_code=500, detail="Trim operation failed")

        from src.audio.metadata import get_duration_ffprobe
        dur = await run_blocking(get_duration_ffprobe, output)

        # Store result in session
        original_name = os.path.splitext(os.path.basename(fpath))[0] + ext
        result_id = _store_result(output, original_name, track_id, "trim")

        return ProcessResult(
            track_id=track_id,
            success=True,
            output_path=output,
            duration_seconds=dur,
            result_id=result_id,
        )
    except HTTPException:
        _cleanup_temp(output)
        raise
    except Exception as e:
        _cleanup_temp(output)
        raise HTTPException(status_code=500, detail=str(e))


# ── Convert ──────────────────────────────────────────────────────────


@router.post("/tracks/{track_id}/convert", response_model=ProcessResult)
async def convert_track(track_id: str, req: ConvertRequest):
    """Convert a track to a different audio format."""
    fpath = _get_track_path(track_id)
    ext = f".{req.target_format}"
    output = _make_temp_output(prefix="conv_", suffix=ext)

    try:
        from src.audio.processor import convert_format
        success = await run_blocking(convert_format, fpath, output, req.target_format)
        if not success:
            _cleanup_temp(output)
            raise HTTPException(
                status_code=500,
                detail=f"Conversion to {req.target_format} failed",
            )

        from src.audio.metadata import get_duration_ffprobe
        dur = await run_blocking(get_duration_ffprobe, output)

        # Store result in session
        original_name = os.path.splitext(os.path.basename(fpath))[0] + ext
        result_id = _store_result(output, original_name, track_id, f"convert_to_{req.target_format}")

        return ProcessResult(
            track_id=track_id,
            success=True,
            output_path=output,
            duration_seconds=dur,
            result_id=result_id,
        )
    except HTTPException:
        _cleanup_temp(output)
        raise
    except Exception as e:
        _cleanup_temp(output)
        raise HTTPException(status_code=500, detail=str(e))


# ── Combined process (trim + convert + volume) ────────────────────────


@router.post("/tracks/{track_id}/process", response_model=ProcessResult)
async def process_track(track_id: str, req: ProcessRequest):
    """Process a track: trim + convert + volume adjustment in one pass."""
    fpath = _get_track_path(track_id)
    ext = f".{req.target_format}"
    output = _make_temp_output(prefix="proc_", suffix=ext)

    try:
        from src.audio.processor import process_and_convert
        success = await run_blocking(
            process_and_convert,
            fpath,
            output,
            req.target_format,
            start_time=req.start_time,
            end_time=req.end_time,
            volume_gain_db=req.volume_gain_db,
        )
        if not success:
            _cleanup_temp(output)
            raise HTTPException(status_code=500, detail="Combined processing failed")

        from src.audio.metadata import get_duration_ffprobe
        dur = await run_blocking(get_duration_ffprobe, output)

        # Store result in session
        original_name = os.path.splitext(os.path.basename(fpath))[0] + ext
        result_id = _store_result(output, original_name, track_id, "process")

        return ProcessResult(
            track_id=track_id,
            success=True,
            output_path=output,
            duration_seconds=dur,
            result_id=result_id,
        )
    except HTTPException:
        _cleanup_temp(output)
        raise
    except Exception as e:
        _cleanup_temp(output)
        raise HTTPException(status_code=500, detail=str(e))
