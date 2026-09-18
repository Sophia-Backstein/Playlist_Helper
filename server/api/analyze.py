"""Volume analysis API endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from server.main import SESSION
from server.models.schemas import AnalyzeResponse
from server.utils.async_utils import run_blocking

router = APIRouter()


@router.post("/tracks/{track_id}/analyze", response_model=AnalyzeResponse)
async def analyze_track(track_id: str):
    """Run full volume analysis on a track."""
    fpath = SESSION["track_files"].get(track_id)
    if not fpath or not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

    try:
        from src.audio.analyzer import (
            analyze_volume_ffmpeg,
            compute_cleaned_average,
            compute_loudest_average,
        )
        vol = await run_blocking(analyze_volume_ffmpeg, fpath)
        cleaned = await run_blocking(compute_cleaned_average, fpath)
        loudest = await run_blocking(compute_loudest_average, fpath)

        return AnalyzeResponse(
            track_id=track_id,
            mean_volume_db=vol.get("mean_volume", 0.0),
            max_volume_db=vol.get("max_volume", 0.0),
            cleaned_average_db=cleaned,
            loudest_average_db=loudest,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
