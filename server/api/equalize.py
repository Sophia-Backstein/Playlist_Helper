"""Equalization API endpoints: equalize-to-average and equalize-to-loudest."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from server.main import SESSION, next_result_id
from server.utils.async_utils import run_blocking
from server.models.schemas import (
    EqualizeAverageRequest,
    EqualizeLoudestRequest,
    EqualizeResult,
)

router = APIRouter()


def _store_eq_result(file_path: str, original_name: str, track_id: str, mode: str) -> str:
    """Store an equalization result in the session and return a result_id."""
    rid = next_result_id()
    SESSION.setdefault("results", {})[rid] = {
        "file_path": file_path,
        "original_name": original_name,
        "track_id": track_id,
        "operation": f"equalize_{mode}",
    }
    return rid


@router.post("/equalize/average", response_model=list[EqualizeResult])
async def equalize_average(req: EqualizeAverageRequest):
    """Equalize multiple tracks to a target average volume."""
    from src.audio.equalizer import equalize_to_average as eq_avg

    results: list[EqualizeResult] = []
    for tid in req.track_ids:
        fpath = SESSION["track_files"].get(tid)
        if not fpath or not os.path.exists(fpath):
            results.append(EqualizeResult(
                track_id=tid, success=False, error="Track not found",
            ))
            continue

        try:
            output = await run_blocking(eq_avg, fpath, req.target_db)
            if output and os.path.exists(output):
                original_name = os.path.basename(fpath)
                ext = os.path.splitext(original_name)[1]
                out_name = os.path.splitext(original_name)[0] + "_equalized" + ext
                result_id = _store_eq_result(output, out_name, tid, "average")
                results.append(EqualizeResult(
                    track_id=tid, success=True, output_path=output, result_id=result_id,
                ))
            else:
                results.append(EqualizeResult(
                    track_id=tid, success=False, error="Equalization produced no output",
                ))
        except Exception as e:
            results.append(EqualizeResult(
                track_id=tid, success=False, error=str(e),
            ))

    return results


@router.post("/equalize/loudest", response_model=list[EqualizeResult])
async def equalize_loudest(req: EqualizeLoudestRequest):
    """Equalize multiple tracks based on the loudest average."""
    from src.audio.equalizer import equalize_to_loudest as eq_loud

    results: list[EqualizeResult] = []
    for tid in req.track_ids:
        fpath = SESSION["track_files"].get(tid)
        if not fpath or not os.path.exists(fpath):
            results.append(EqualizeResult(
                track_id=tid, success=False, error="Track not found",
            ))
            continue

        try:
            output = await run_blocking(eq_loud, fpath, target_db=req.target_db)
            if output and os.path.exists(output):
                original_name = os.path.basename(fpath)
                ext = os.path.splitext(original_name)[1]
                out_name = os.path.splitext(original_name)[0] + "_equalized" + ext
                result_id = _store_eq_result(output, out_name, tid, "loudest")
                results.append(EqualizeResult(
                    track_id=tid, success=True, output_path=output, result_id=result_id,
                ))
            else:
                results.append(EqualizeResult(
                    track_id=tid, success=False, error="Equalization produced no output",
                ))
        except Exception as e:
            results.append(EqualizeResult(
                track_id=tid, success=False, error=str(e),
            ))

    return results
